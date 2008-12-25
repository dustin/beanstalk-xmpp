#!/usr/bin/env python

from collections import defaultdict

from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from wokkel.xmppim import MessageProtocol, PresenceClientProtocol
from wokkel.xmppim import AvailablePresence

import config

import beanstalk

class BeanstalkXMPPProtocol(MessageProtocol, PresenceClientProtocol):

    def __init__(self):
        super(BeanstalkXMPPProtocol, self).__init__()

    def connectionInitialized(self):
        MessageProtocol.connectionInitialized(self)
        PresenceClientProtocol.connectionInitialized(self)
        self.statii = {}
        self.ignoring = defaultdict(set)

    def connectionMade(self):
        print "Connected!"
        self.available(None, None, {None: 'To Serve Man'})

    def connectionLost(self, reason):
        print "Disconnected!"

    def typing_notification(self, jid):
        """Send a typing notification to the given jid."""

        msg = domish.Element((None, "message"))
        msg["to"] = jid
        msg["from"] = config.SCREEN_NAME
        msg.addElement(('jabber:x:event', 'x')).addElement("composing")

        self.send(msg)

    def send_plain(self, jid, content, type='chat'):
        msg = domish.Element((None, "message"))
        msg["to"] = jid
        msg["from"] = config.SCREEN_NAME
        msg["type"] = type
        msg.addElement("body", content=content)

        self.send(msg)

    def willing_to_receive(self, jid, group):
        print "Seeing if %s wants %s" % (jid, group)
        return not (self.statii[jid] in ['dnd', 'unavailable']
            or jid in self.ignoring[group])

    def broadcast(self, msg):
        print "Broadcasting", repr(msg)
        grp, rest = msg.split(' ', 1)
        for jid in self.statii.keys():
            if jid != config.SCREEN_NAME and self.willing_to_receive(jid, grp):
                print "Sending to", jid
                self.send_plain(jid, msg)

    def onMessage(self, msg):
        if hasattr(msg, "body") and msg.body and msg["type"] == 'chat':
            self.typing_notification(msg['from'])
            a=unicode(msg.body).split(' ', 2)
            f=None
            try:
                f=getattr(self, "cmd_" + a[0])
            except AttributeError:
                self.send_plain(msg['from'],
                    "Unknown command: %s (try help)" % a[0])

            if f:
                f(msg['from'], *a[1:])

    def cmd_ignore(self, jid, group):
        "ignore a group"
        self.ignoring[group].add(jid)
        self.send_plain(jid, "You're now ignoring " + group)

    def cmd_watch(self, jid, group):
        "watch (stop ignoring) a group"
        self.ignoring[group].remove(jid)
        self.send_plain(jid, "You're now watching " + group)

    def cmd_ignoring(self, jid):
        "list all the groups you're ignoring"
        rv = ["Stuff you're ignoring"]
        for k,v in self.ignoring.iteritems():
            if jid in v:
                rv.append("- " + k)

        self.send_plain(jid, '\n'.join(rv))

    def cmd_help(self, jid):
        "this help"
        helptext=["Help on commands"]
        for c in sorted(dir(self)):
            if c.find("cmd_") == 0:
                f = getattr(self, c)
                helptext.append("%s:  %s" % (c[4:], f.__doc__))
        self.send_plain(jid, "\n".join(helptext))

    # presence stuff
    def availableReceived(self, entity, show=None, statuses=None, priority=0):
        print "Available from %s (%s, %s)" % (entity.full(), show, statuses)
        self.statii[entity.full()] = show

    def unavailableReceived(self, entity, statuses=None):
        print "Unavailable from %s" % entity.userhost()
        del self.statii[entity.full()]

    def subscribedReceived(self, entity):
        print "Subscribe received from %s" % (entity.userhost())
        welcome_message="""Welcome to beanstalk-xmpp."""
        self.send_plain(entity.full(), welcome_message)

    def unsubscribedReceived(self, entity):
        print "Unsubscribed received from %s" % (entity.userhost())
        self.unsubscribe(entity)
        self.unsubscribed(entity)

    def subscribeReceived(self, entity):
        print "Subscribe received from %s" % (entity.userhost())
        self.subscribe(entity)
        self.subscribed(entity)

    def unsubscribeReceived(self, entity):
        print "Unsubscribe received from %s" % (entity.userhost())
        self.unsubscribe(entity)
        self.unsubscribed(entity)
