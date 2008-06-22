#!/usr/bin/env ruby

require 'rubygems'
require 'date'
require 'xmpp4r-simple'
require 'beanstalk-client'

CONF = YAML.load_file 'jabber-bot.yml'

JABBER = Jabber::Simple.new(CONF['xmpp']['jid'], CONF['xmpp']['pass'])

BEANSTALK = Beanstalk::Pool.new [CONF['beanstalk']['server']]
BEANSTALK.watch CONF['beanstalk']['tube']
BEANSTALK.ignore 'default'

TIMEOUT = CONF['general']['timeout'].to_i

STATII = {}

def process_xmpp_incoming
  JABBER.presence_updates { |user, status, message| STATII[user] = status }
  JABBER.received_messages do |msg|
    JABBER.deliver msg.from,
      "Sorry, I don't understand you.  I'm just here to tell you about stuff."
  end
  JABBER.new_subscriptions { |from, presence| puts "Subscribed by #{from}" }
  JABBER.subscription_requests { |from, presence| puts "Sub req from #{from}" }
end

def process_job(job)
  to, msg = job.body.split(/\s+/, 2)
  msg = msg.strip
  puts "Got #{msg} for #{to}"
  if to == 'status'
    JABBER.status nil, msg
  else
    if STATII.has_key?(to) && ! [:dnd, :unavailable].include?(STATII[to])
      puts "Delivering message to #{to} #{STATII[to]}"
      JABBER.deliver to, msg
    end
  end
end

def run_loop
  job = begin
    puts "Waiting for a message at #{Time.now.to_s}"
    $stdout.flush
    BEANSTALK.reserve TIMEOUT
  rescue Beanstalk::TimedOut
    nil
  end
  puts "Processing #{job} at #{Time.now.to_s}"
  $stdout.flush
  process_xmpp_incoming
  process_job job if job
rescue StandardError, Interrupt
  puts "Got exception:  #{$!.inspect}"
  sleep 5
  if job
    job.decay
    job = nil
  end
ensure
  job.delete if job
end

loop do
  run_loop
end
