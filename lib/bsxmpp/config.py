#!/usr/bin/env python
"""
Configuration for beanstalk-xmpp.

Copyright (c) 2008  Dustin Sallings <dustin@spy.net>
"""

import ConfigParser
import commands

CONF=ConfigParser.ConfigParser()
CONF.read('beanstalk-xmpp.conf')
SCREEN_NAME = CONF.get('xmpp', 'jid')
VERSION=commands.getoutput("git describe").strip()
