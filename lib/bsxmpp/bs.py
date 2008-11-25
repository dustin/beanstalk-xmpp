#!/usr/bin/env python
"""
The beanstalk stuff.

Copyright (c) 2008  Dustin Sallings <dustin@spy.net>
"""

from twisted.internet import reactor, protocol, defer, task

import beanstalk

class BSFactory(protocol.ReconnectingClientFactory):

    def __init__(self, xmpp):
        self.xmpp=xmpp

    def connectedCallback(self, cb):
        self.__connectedCallback = cb
        return self

    def disconnectedCallback(self, cb):
        self.__disconnectedCallback = cb
        return self

    def buildProtocol(self, addr):
        self.resetDelay()
        print "Connected to beanstalkd."
        bs = beanstalk.Beanstalk()
        if self.__connectedCallback:
            reactor.callLater(0, self.__connectedCallback, bs)
        return bs

    def disco(self, connector, reason):
        if self.__disconnectedCallback:
            reactor.callLater(0, self.__disconnectedCallback, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        protocol.ReconnectingClientFactory.clientConnectionFailed(self,
            connector, reason)
        self.disco(connector, reason)

    def clientConnectionLost(self, connector, reason):
        protocol.ReconnectingClientFactory.clientConnectionLost(self,
            connector, reason)
        self.disco(connector, reason)

def __gotJob(bs, xmpp, jobid, jobdata):
    print "Got job", jobid, repr(jobdata)
    xmpp.broadcast(jobdata)
    bs.delete(jobid)

def __executionGenerator(xmpp, bs):
    while True:
        yield bs.reserve().addCallback(lambda v: __gotJob(bs, xmpp, *v))

def __worker(xmpp, coop):
    def f(bs):
        print "Starting worker..."
        bs.watch("xmpp")
        bs.ignore("default")
        coop.coiterate(__executionGenerator(xmpp, bs))
    return f

def __shutdown(coop):
    def f(c, r):
        coop.stop()
    return f

def connectBeanstalk(xmpp, host, port=11300):
    coop = task.Cooperator()
    factory = BSFactory(xmpp).connectedCallback(
        __worker(xmpp, coop)).disconnectedCallback(
        __shutdown(coop))
    reactor.connectTCP(host, port, factory)
