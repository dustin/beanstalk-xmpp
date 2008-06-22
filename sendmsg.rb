#!/usr/bin/env ruby -w

require 'rubygems'
require 'beanstalk-client'

begin
  CONF = YAML.load_file 'jabber-bot.yml'
rescue Errno::ENOENT
  unless ENV.has_key?('BEANSTALK_SERVER') && ENV.has_key?('BEANSTALK_TUBE')
    raise "No jabber-bot.yml or BEANSTALK_SERVER and BEANSTALK_TUBE env"
  end
  CONF = { 'beanstalk' => {
    'server' => ENV['BEANSTALK_SERVER'],
    'tube' => ENV['BEANSTALK_TUBE']
    }}
end

BEANSTALK = Beanstalk::Pool.new [CONF['beanstalk']['server']]
BEANSTALK.use CONF['beanstalk']['tube']

# Add the commandline into the queue.
BEANSTALK.put $*.join(' ')
