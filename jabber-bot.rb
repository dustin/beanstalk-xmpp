#!/usr/bin/env ruby

require 'rubygems'
require 'date'
require 'set'
require 'xmpp4r'
require 'xmpp4r/roster'
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

class BotMain

  def initialize(jid, pass)
    @statii = {}
    @user_status = Hash.new :on
    @ignoring = Hash.new {|h,k| h[k] = Set.new; h[k]}

    @client = Jabber::Client.new(jid)
    @client.connect
    @client.auth(pass)

    setup_callbacks

    @client.send(Jabber::Presence.new(nil,
      CONF['xmpp']['status'] || 'To Serve Man',
      (CONF['xmpp']['priority'] || 1).to_i))
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

  def subscribe_to(jid)
    puts "Sending subscription request to #{jid}"
    req = Jabber::Presence.new.set_type(:subscribe)
    req.to = jid
    @client.send req
  end

  def setup_callbacks

    @client.on_exception do |e, stream, symbol|
      puts "Exception in #{symbol}: #{e}" + e.backtrace.join("\n\t")
      $stdout.flush
    end

    @roster = Jabber::Roster::Helper.new(@client)

    @roster.add_subscription_request_callback do |roster_item, presence|
      puts "Subscription requrest from #{presence.from.to_s}"
      @roster.accept_subscription(presence.from)
      subscribe_to presence.from.bare.to_s
    end

    @client.add_presence_callback do |presence|
      status = presence.type.nil? ? :available : presence.type
      @statii[presence.from.bare.to_s] = status
      puts "*** #{presence.from} -> #{status}"
      $stdout.flush
    end

    @client.add_message_callback do |msg|
      begin
        unless msg.body.nil?
          puts "<<< Received message from #{msg.from} #{msg.body}"
          cmd, args = msg.body.split /\s+/, 2
          cmd_method = "cmd_#{cmd}".to_sym
          if self.respond_to? cmd_method
            self.send cmd_method, msg.from, args
          else
            deliver msg.from, "I don't understand #{cmd}"
          end
        end
      rescue StandardError, Interrupt
        puts "Incoming message error:  #{$!}\n" + $!.backtrace.join("\n\t")
        $stdout.flush
        deliver message.from, "Error processing your message:  #{$!}"
      end
    end
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

  def deliver(jid, message, type=:chat)
    if message.kind_of?(Jabber::Message)
      msg = message
      msg.to = jid
    else
      msg = Jabber::Message.new(jid)
      msg.type = type
      msg.body = message
    end
    @client.send msg
  end

end

# Jabber::debug = true

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

jabber = BotMain.new(CONF['xmpp']['jid'], CONF['xmpp']['pass'])

loop do
  run_loop jabber
end
