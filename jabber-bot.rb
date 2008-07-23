#!/usr/bin/env ruby

require 'rubygems'
require 'date'
require 'set'
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

class MyClient < Jabber::Simple

  def initialize(jid, pass)
    super(jid, pass)

    @statii = {}
    @user_status = Hash.new :on
    @ignoring = Hash.new {|h,k| h[k] = Set.new; h[k]}

    setup_callback
  end
    
  def reconnect
    puts "Reconnecting"
    $stdout.flush
    super
    setup_callback
  end

  def willing_to_receive(jid, to)
    !([:dnd, :unavailable].include?(@statii[jid]) || @ignoring[to].include?(jid))
  end

  def process_job(job)
    to, msg = job.body.split(/\s+/, 2)
    msg = msg.strip
    puts "Got #{msg} for #{to}"
    if to == 'status'
      status nil, msg
    else
      @statii.keys.each do |jid|
        if willing_to_receive(jid, to)
          puts "Delivering message to #{jid} (#{@statii[jid]})"
          deliver jid, msg
        end
      end
    end
  end

  def process_xmpp_incoming
    presence_updates { |user, status, message| @statii[user] = status }
    received_messages
    new_subscriptions { |from, presence| puts "Subscribed by #{from}" }
    subscription_requests { |from, presence| puts "Sub req from #{from}" }
  end

  def cmd_ignore(from, group)
    @ignoring[group] << from.bare.to_s
    deliver from, "You're now ignoring ``#{group}''"
  end

  def cmd_watch(from, group)
    @ignoring[group].delete from.bare.to_s
    deliver from, "You're no longer ignoring ``#{group}''"
  end

  def cmd_ignoring(from, whatever)
    i=@ignoring.to_a.select{|k,v| v.include? from.bare.to_s}.map{|k,v| k}.sort
    if i.empty?
      deliver from, "You're not ignoring anything."
    else
      deliver from, "Ignoring: #{i.join ', '}"
    end
  end

  def setup_callback
    client.add_message_callback do |msg|
      begin
        cmd, args = msg.body.split /\s+/, 2
        puts "<<< Received message from #{msg.from} #{msg.body}"
        cmd_method = "cmd_#{cmd}".to_sym
        if self.respond_to? cmd_method
          self.send cmd_method, msg.from, args
        else
          deliver msg.from, "I don't understand #{cmd}"
        end
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
  jabber.process_xmpp_incoming
  jabber.process_job job if job
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
