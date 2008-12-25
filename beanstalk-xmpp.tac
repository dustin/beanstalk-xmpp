import sys
sys.path.append("lib")
sys.path.append("lib/wokkel")

import ConfigParser

from twisted.application import service
from twisted.internet import task, reactor
from twisted.words.protocols.jabber import jid
from wokkel.client import XMPPClient
from wokkel.generic import VersionHandler
from wokkel.keepalive import KeepAlive

from bsxmpp import config
from bsxmpp import protocol
from bsxmpp import bs

application = service.Application("beanstalk-xmpp")

host = None
try:
    host = config.CONF.get("xmpp", 'host')
except ConfigParser.NoOptionError:
    pass

xmppclient = XMPPClient(jid.internJID(config.SCREEN_NAME),
    config.CONF.get('xmpp', 'pass'), host)
xmppclient.logTraffic = False
bp=protocol.BeanstalkXMPPProtocol()
bp.setHandlerParent(xmppclient)
VersionHandler('beanstalk-xmpp', config.VERSION).setHandlerParent(xmppclient)
KeepAlive().setHandlerParent(xmppclient)

b = bs.connectBeanstalk(bp, config.CONF.get('beanstalk', 'host'),
    config.CONF.getint('beanstalk', 'port'))

xmppclient.setServiceParent(application)

