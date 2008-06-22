# A Stupidly Simple Beanstalk -> Jabber Gateway

I've got various things that run that are written in various languages.  Some
of those languages don't have XMPP libraries available (or at least, easy to
use ones), but most have a [beanstalk](http://xph.us/software/beanstalkd/)
interface.  The ones that don't can have one very easily.

This bot sits on a beanstalk tube and waits for simple messages to arrive and
follows their instructions.  The message structure is excessively simple.

Messages will *not* be delivered if the user is offline, or the user's status
is set to `dnd` (do not disturb).

## Message Structure

    [recipient] [various text]

`recipient` may be either `status` to update the bot's status, or an IM name
to send an IM to that user.  The remaining text is what gets set as the status
or delivered.

## Examples

### Setting the Bot's Status

    status Look, I have a new status now.

### Sending an IM

    user@example.com Holy crap, something just went wrong.