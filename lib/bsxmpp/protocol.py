#!/usr/bin/env python

from twisted.internet import task
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from wokkel.xmppim import MessageProtocol, PresenceClientProtocol
from wokkel.xmppim import AvailablePresence
from wokkel.client import XMPPHandler

import config

import beanstalk

class BeanstalkXMPPProtocol(MessageProtocol, PresenceClientProtocol):

    def __init__(self):
        super(BeanstalkXMPPProtocol, self).__init__()

    def connectionInitialized(self):
        MessageProtocol.connectionInitialized(self)
        PresenceClientProtocol.connectionInitialized(self)
        self.statii = {}

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

    def broadcast(self, msg):
        print "Broadcasting", repr(msg)
        for jid in self.statii.keys():
            if jid != config.SCREEN_NAME:
                print "Sending to", jid
                self.send_plain(jid, msg)

    def onMessage(self, msg):
        if hasattr(msg, "body") and msg.body and msg["type"] == 'chat':
            self.typing_notification(msg['from'])
            a=unicode(msg.body).split(' ', 1)
            # XXX:  ignore, watch, ignoring
            self.send_plain(msg['from'], 'Incoming not handled yet.', 'error')

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

# From https://mailman.ik.nu/pipermail/twisted-jabber/2008-October/000171.html
class KeepAlive(XMPPHandler):

    interval = 300
    lc = None

    def connectionInitialized(self):
        self.lc = task.LoopingCall(self.ping)
        self.lc.start(self.interval)

    def connectionLost(self, *args):
        if self.lc:
            self.lc.stop()

    def ping(self):
        print "Stayin' alive"
        self.send(" ")
