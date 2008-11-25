from twisted.protocols import basic
from twisted.internet import defer, protocol
from twisted.python import log
from StringIO import StringIO

# Stolen from memcached protocol
try:
    from collections import deque
except ImportError:
    class deque(list):
        def popleft(self):
            return self.pop(0)

class Command(object):
    """
    Wrap a client action into an object, that holds the values used in the
    protocol.

    @ivar _deferred: the L{Deferred} object that will be fired when the result
        arrives.
    @type _deferred: L{Deferred}

    @ivar command: name of the command sent to the server.
    @type command: C{str}
    """

    def __init__(self, command, **kwargs):
        """
        Create a command.

        @param command: the name of the command.
        @type command: C{str}

        @param kwargs: this values will be stored as attributes of the object
            for future use
        """
        self.command = command
        self._deferred = defer.Deferred()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return "<Command: %s>" % self.command

    def success(self, value):
        """
        Shortcut method to fire the underlying deferred.
        """
        self._deferred.callback(value)


    def fail(self, error):
        """
        Make the underlying deferred fails.
        """
        self._deferred.errback(error)

class UnexpectedResponse(Exception): pass

class TimedOut(Exception): pass

class NotFound(Exception): pass

class BadFormat(Exception): pass

class InternalError(Exception): pass

class Draining(Exception): pass

class UnknownCommand(Exception): pass

class OutOfMemory(Exception): pass

class ExpectedCRLF(Exception): pass

class JobTooBig(Exception): pass

class DeadlineSoon(Exception): pass

class NotIgnored(Exception): pass

class Beanstalk(basic.LineReceiver):

    __ERRORS={'TIMED_OUT': TimedOut, 'NOT_FOUND': NotFound,
        'BAD_FORMAT': BadFormat, 'INTERNAL_ERROR': InternalError,
        'DRAINING': Draining, 'UNKNOWN_COMMAND': UnknownCommand,
        'OUT_OF_MEMORY': OutOfMemory, 'EXPECTED_CRLF': ExpectedCRLF,
        'JOB_TOO_BIG': JobTooBig, 'DEADLINE_SOON': DeadlineSoon,
        'NOT_IGNORED': NotIgnored}

    def __init__(self):
        self._current = deque()
        self._lenExpected = None
        self._getBuffer = None
        self._bufferLength = None

    def rawDataRecevied(self, data):
        self.current_command=None

    def connectionMade(self):
        print "Connected!"
        self.setLineMode()

    def __cmd(self, command, full_command, *args, **kwargs):
        self.sendLine(full_command)
        cmdObj = Command(command, **kwargs)
        self._current.append(cmdObj)
        return cmdObj._deferred

    def stats(self):
        return self.__cmd('stats', 'stats')

    def stats_job(self, id):
        return self.__cmd('stats-job', 'stats-job %d' % id)

    def stats_tube(self, name):
        return self.__cmd('stats-tube', 'stats-tube %s' % name)

    def use(self, tube):
        return self.__cmd('use', 'use %s' % tube, tube=tube)

    def watch(self, tube):
        return self.__cmd('watch', 'watch %s' % tube, tube=tube)

    def ignore(self, tube):
        return self.__cmd('ignore', 'ignore %s' % tube, tube=tube)

    def put(self, pri, delay, ttr, data):
        fullcmd = "put %d %d %d %d" % (pri, delay, ttr, len(data))
        self.sendLine(fullcmd)
        self.sendLine(data)
        cmdObj = Command('put')
        self._current.append(cmdObj)
        return cmdObj._deferred

    def reserve(self, timeout=None):
        if timeout:
            cmd="reserve-with-timeout %d" % timeout
        else:
            cmd="reserve"
        return self.__cmd('reserve', cmd)

    def delete(self, job):
        return self.__cmd('delete', 'delete %d' % job)

    def touch(self, job):
        return self.__cmd('touch', 'touch %d' % job)

    def list_tubes(self):
        return self.__cmd('list-tubes', 'list-tubes')

    def list_tubes_watched(self):
        return self.__cmd('list-tubes-watched', 'list-tubes-watched')

    def used_tube(self):
        return self.__cmd('list-tube-used', 'list-tube-used')

    def release(self, job, pri, delay):
        return self.__cmd('release', 'release %d %d %d' % (job, pri, delay))

    def bury(self, job, pri):
        return self.__cmd('bury', 'bury %d %d' % (job, pri))

    def kick(self, bound):
        return self.__cmd('kick', 'kick %d' % bound)

    def peek(self, id):
        return self.__cmd('peek', 'peek %d' % id)

    def peek_ready(self):
        return self.__cmd('peek-ready', 'peek-ready')

    def peek_delayed(self):
        return self.__cmd('peek-delayed', 'peek-delayed')

    def peek_buried(self):
        return self.__cmd('peek-buried', 'peek-buried')

    def __success(self, val):
        cmd = self._current.popleft()
        cmd.success(val)

    def __int_success(self, val): self.__success(int(val))

    def __null_success(self): self.__success(None)

    _cmd_USING = __success

    _cmd_KICKED = __int_success

    _cmd_DELETED = __null_success

    _cmd_TOUCHED = __null_success

    _cmd_RELEASED = __null_success

    _cmd_WATCHING = __int_success

    def _cmd_INSERTED(self, line):
        self.__success((True, int(line)))

    def _cmd_BURIED(self, *args):
        if args:
            self.__success((False, int(args[0])))
        else:
            self.__success(None)

    def __blob_response(self, cmd, length):
        self._lenExpected = length
        self._getBuffer = []
        self._bufferLength = 0
        cmd.length = self._lenExpected
        self.setRawMode()

    def _cmd_OK(self, line):
        self.__blob_response(self._current[0], int(line))

    def __parse_job_response(self, line):
        i, length=line.split(' ')
        cmd=self._current[0]
        cmd.id=int(i)
        self.__blob_response(cmd, int(length))

    _cmd_RESERVED = __parse_job_response

    _cmd_FOUND = __parse_job_response

    def lineReceived(self, line):
        """
        Receive line commands from the server.
        """
        token = line.split(" ", 1)[0]
        if self.__ERRORS.has_key(token):
            cmd = self._current.popleft()
            cmd.fail(self.__ERRORS[token]())
            return
        # First manage standard commands without space
        cmd = getattr(self, "_cmd_%s" % (token,), None)
        if cmd is not None:
            args = line.split(" ", 1)[1:]
            if args:
                cmd(args[0])
            else:
                cmd()
        else:
            pending = self._current.popleft()
            pending.fail(UnexpectedResponse(line))

    def __parseStats(self, v):
        lines=v.strip().split("\n")[1:]
        return dict([l.split(": ") for l in lines])

    def __parseList(self, v):
        lines=v.strip().split("\n")[1:]
        return [l[2:] for l in lines]

    def rawDataReceived(self, data):
        self._getBuffer.append(data)
        self._bufferLength += len(data)
        if self._bufferLength >= self._lenExpected + 2:
            data = "".join(self._getBuffer)
            buf = data[:self._lenExpected]
            rem = data[self._lenExpected + 2:]
            val = buf
            self._lenExpected = None
            self._getBuffer = None
            self._bufferLength = None
            cmd = self._current[0]
            cmd.value = val
            x = self._current.popleft()
            if cmd.command == 'reserve':
                cmd.success((cmd.id, cmd.value))
            elif cmd.command in ['stats', 'stats-job', 'stats-tube']:
                cmd.success(self.__parseStats(cmd.value))
            elif cmd.command in ['peek', 'peek-ready',
                'peek-delayed', 'peek-buried']:
                cmd.success((cmd.id, cmd.value))
            elif cmd.command in ['list-tubes', 'list-tubes-watched']:
                cmd.success(self.__parseList(cmd.value))

            self.setLineMode(rem)

class BeanstalkClientFactory(protocol.ClientFactory):
    def startedConnecting(self, connector):
        print 'Started to connect.'

    def buildProtocol(self, addr):
        print 'Connected.'
        return Beanstalk()

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection.  Reason:', reason

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed. Reason:', reason
