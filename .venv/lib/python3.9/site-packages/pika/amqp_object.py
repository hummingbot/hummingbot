"""Base classes that are extended by low level AMQP frames and higher level
AMQP classes and methods.

"""


class AMQPObject(object):
    """Base object that is extended by AMQP low level frames and AMQP classes
    and methods.

    """
    NAME = 'AMQPObject'
    INDEX = None

    def __repr__(self):
        items = list()
        for key, value in self.__dict__.items():
            if getattr(self.__class__, key, None) != value:
                items.append('%s=%s' % (key, value))
        if not items:
            return "<%s>" % self.NAME
        return "<%s(%s)>" % (self.NAME, sorted(items))

    def __eq__(self, other):
        if other is not None:
            return self.__dict__ == other.__dict__
        else:
            return False


class Class(AMQPObject):
    """Is extended by AMQP classes"""
    NAME = 'Unextended Class'


class Method(AMQPObject):
    """Is extended by AMQP methods"""
    NAME = 'Unextended Method'
    synchronous = False

    def _set_content(self, properties, body):
        """If the method is a content frame, set the properties and body to
        be carried as attributes of the class.

        :param pika.frame.Properties properties: AMQP Basic Properties
        :param bytes body: The message body

        """
        self._properties = properties  # pylint: disable=W0201
        self._body = body  # pylint: disable=W0201

    def get_properties(self):
        """Return the properties if they are set.

        :rtype: pika.frame.Properties

        """
        return self._properties

    def get_body(self):
        """Return the message body if it is set.

        :rtype: str|unicode

        """
        return self._body


class Properties(AMQPObject):
    """Class to encompass message properties (AMQP Basic.Properties)"""
    NAME = 'Unextended Properties'
