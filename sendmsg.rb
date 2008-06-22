#!/usr/bin/env ruby -w

require 'rubygems'
require 'beanstalk-client'

CONF = YAML.load_file 'jabber-bot.yml'

BEANSTALK = Beanstalk::Pool.new [CONF['beanstalk']['server']]
BEANSTALK.use CONF['beanstalk']['tube']

# Add the commandline into the queue.
BEANSTALK.put $*.join(' ')
