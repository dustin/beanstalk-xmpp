#!/usr/bin/env ruby

require 'rubygems'
require 'date'
require 'xmpp4r-simple'
require 'beanstalk-client'

CONF_PATHS = [
  "jabber-bot.yml", "/usr/local/etc/jabber-bot.yml", "/etc/jabber-bot.yml"
]

CONF_PATH = CONF_PATHS.detect { |f| File.exist? f }

unless CONF_PATH
  puts "Expected to find a config in one of\n\t#{CONF_PATHS.join("\n\t")}"
  exit 1
end

CONF = YAML.load_file CONF_PATH

BEANSTALK = Beanstalk::Pool.new [CONF['beanstalk']['server']]
BEANSTALK.watch CONF['beanstalk']['tube']
BEANSTALK.ignore 'default'

TIMEOUT = CONF['general']['timeout'].to_i

STATII = {}
USER_STATUS = Hash.new :on

def process_xmpp_incoming(jabber)
  jabber.presence_updates { |user, status, message| STATII[user] = status }
  jabber.received_messages
  jabber.new_subscriptions { |from, presence| puts "Subscribed by #{from}" }
  jabber.subscription_requests { |from, presence| puts "Sub req from #{from}" }
end

def process_job(jabber, job)
  to, msg = job.body.split(/\s+/, 2)
  msg = msg.strip
  puts "Got #{msg} for #{to}"
  if to == 'status'
    jabber.status nil, msg
  else
    if STATII.has_key?(to) && ! [:dnd, :unavailable].include?(STATII[to])
      puts "Delivering message to #{to} #{STATII[to]}"
      jabber.deliver to, msg
    end
  end
end

class MyClient < Jabber::Simple

  def initialize(jid, pass)
    super(jid, pass)
    setup_callback
  end
    
  def reconnect
    puts "Reconnecting"
    $stdout.flush
    super
    setup_callback
  end

  def setup_callback
    client.add_message_callback do |msg|
      begin
        puts "<<< Received message from #{msg.from} #{msg.body}"
        deliver msg.from,
          "Sorry, I don't understand you.  I'm just here to tell you about stuff."
      rescue StandardError, Interrupt
        puts "Incoming message error:  #{$!}\n" + $!.backtrace.join("\n\t")
        $stdout.flush
        deliver message.from, "Error processing your message:  #{$!}"
      end
    end
  end
end

def run_loop(jabber)
  job = begin
    puts "Waiting for a message at #{Time.now.to_s}"
    $stdout.flush
    BEANSTALK.reserve TIMEOUT
  rescue Beanstalk::TimedOut
    nil
  end
  puts "Processing #{job} at #{Time.now.to_s}"
  $stdout.flush
  process_xmpp_incoming jabber
  process_job jabber, job if job
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

jabber = MyClient.new(CONF['xmpp']['jid'], CONF['xmpp']['pass'])
jabber.send!(Jabber::Presence.new(nil,
  CONF['xmpp']['status'] || 'In service',
  (CONF['xmpp']['priority'] || 1).to_i))

loop do
  run_loop jabber
end
