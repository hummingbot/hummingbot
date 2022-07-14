# The version of the protocol we implement.
STOMP_VERSION = '1.1'

# STOMP Spec v1.1 valid commands:
VALID_COMMANDS = [
    'ABORT', 'ACK', 'BEGIN', 'COMMIT',
    'CONNECT', 'CONNECTED', 'DISCONNECT', 'MESSAGE',
    'NACK', 'SEND', 'SUBSCRIBE', 'UNSUBSCRIBE',
    'RECEIPT', 'ERROR',
]

# Message terminator:
NULL = '\x00'


def subscribe(dest, idx, ack='auto'):
    """STOMP subscribe command.

    dest:
        This is the channel we wish to subscribe to

    idx:
        The ID that should uniquely identify the subscription

    ack: 'auto' | 'client'
        If the ack is set to client, then messages received will
        have to have an acknowledge as a reply. Otherwise the server
        will assume delivery failure.

    """
    return "SUBSCRIBE\nid:%s\ndestination:%s\nack:%s\n\n\x00\n" % (idx, dest, ack)


class FrameError(Exception):
    """Raise for problem with frame generation or parsing.
    """


class Frame(object):
    """This class is used to create or read STOMP message frames.

    The method pack() is used to create a STOMP message ready
    for transmission.

    The method unpack() is used to read a STOMP message into
    a frame instance. It uses the unpack_frame(...) function
    to do the initial parsing.

    The frame has three important member variables:

      * cmd
      * headers
      * body

    The 'cmd' is a property that represents the STOMP message
    command. When you assign this a check is done to make sure
    its one of the VALID_COMMANDS. If not then FrameError will
    be raised.

    The 'headers' is a dictionary which the user can added to
    if needed. There are no restrictions or checks imposed on
    what values are inserted.

    The 'body' is just a member variable that the body text
    is assigned to.

    """

    def __init__(self):
        """Setup the internal state."""
        self._cmd = ''
        self.body = ''
        self.headers = {}

    def getCmd(self):
        """Don't use _cmd directly!"""
        return self._cmd

    def setCmd(self, cmd):
        """Check the cmd is valid, FrameError will be raised if its not."""
        cmd = cmd.upper()
        if cmd not in VALID_COMMANDS:
            raise FrameError("The cmd '%s' is not valid! It must be one of '%s' (STOMP v%s)." % (
                cmd, VALID_COMMANDS, STOMP_VERSION))
        else:
            self._cmd = cmd

    cmd = property(getCmd, setCmd)

    def pack(self):
        """Called to create a STOMP message from the internal values.
        """
        headers = ''.join(
            ['%s:%s\n' % (f, v) for f, v in sorted(self.headers.items())]
        )
        stomp_message = "%s\n%s\n%s%s\n" % (self._cmd, headers, self.body, NULL)

        return stomp_message

    def unpack(self, message):
        """Called to extract a STOMP message into this instance.

        message:
            This is a text string representing a valid
            STOMP (v1.1) message.

        This method uses unpack_frame(...) to extract the
        information, before it is assigned internally.

        retuned:
            The result of the unpack_frame(...) call.

        """
        if not message:
            raise FrameError("Unpack error! The given message isn't valid '%s'!" % message)

        msg = unpack_frame(message)

        self.cmd = msg['cmd']
        self.headers = msg['headers']

        # Assign directly as the message will have the null
        # character in the message already.
        self.body = msg['body']

        return msg


def unpack_frame(message):
    """Called to unpack a STOMP message into a dictionary.

    returned = {
        # STOMP Command:
        'cmd' : '...',

        # Headers e.g.
        'headers' : {
            'destination' : 'xyz',
            'message-id' : 'some event',
            :
            etc,
        }

        # Body:
        'body' : '...1234...\x00',
    }

    """
    body = []
    returned = dict(cmd='', headers={}, body='')

    breakdown = message.split('\n')

    # Get the message command:
    returned['cmd'] = breakdown[0]
    breakdown = breakdown[1:]

    def headD(field):
        # find the first ':' everything to the left of this is a
        # header, everything to the right is data:
        index = field.find(':')
        if index:
            header = field[:index].strip()
            data = field[index + 1:].strip()
            #            print "header '%s' data '%s'" % (header, data)
            returned['headers'][header.strip()] = data.strip()

    def bodyD(field):
        field = field.strip()
        if field:
            body.append(field)

    # Recover the header fields and body data
    handler = headD
    for field in breakdown:
        #        print "field:", field
        if field.strip() == '':
            # End of headers, it body data next.
            handler = bodyD
            continue

        handler(field)

    # Stich the body data together:
    #    print "1. body: ", body
    body = "".join(body)
    returned['body'] = body.replace('\x00', '')

    #    print "2. body: <%s>" % returned['body']

    return returned
