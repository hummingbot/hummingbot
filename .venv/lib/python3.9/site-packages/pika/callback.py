"""Callback management class, common area for keeping track of all callbacks in
the Pika stack.

"""
import functools
import logging

from pika import frame
from pika import amqp_object
from pika.compat import xrange, canonical_str

LOGGER = logging.getLogger(__name__)


def name_or_value(value):
    """Will take Frame objects, classes, etc and attempt to return a valid
    string identifier for them.

    :param pika.amqp_object.AMQPObject|pika.frame.Frame|int|str value: The
        value to sanitize
    :rtype: str

    """
    # Is it subclass of AMQPObject
    try:
        if issubclass(value, amqp_object.AMQPObject):
            return value.NAME
    except TypeError:
        pass

    # Is it a Pika frame object?
    if isinstance(value, frame.Method):
        return value.method.NAME

    # Is it a Pika frame object (go after Method since Method extends this)
    if isinstance(value, amqp_object.AMQPObject):
        return value.NAME

    # Cast the value to a str (python 2 and python 3); encoding as UTF-8 on Python 2
    return canonical_str(value)


def sanitize_prefix(function):
    """Automatically call name_or_value on the prefix passed in."""

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        args = list(args)
        offset = 1
        if 'prefix' in kwargs:
            kwargs['prefix'] = name_or_value(kwargs['prefix'])
        elif len(args) - 1 >= offset:
            args[offset] = name_or_value(args[offset])
            offset += 1
        if 'key' in kwargs:
            kwargs['key'] = name_or_value(kwargs['key'])
        elif len(args) - 1 >= offset:
            args[offset] = name_or_value(args[offset])

        return function(*tuple(args), **kwargs)

    return wrapper


def check_for_prefix_and_key(function):
    """Automatically return false if the key or prefix is not in the callbacks
    for the instance.

    """

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        offset = 1
        # Sanitize the prefix
        if 'prefix' in kwargs:
            prefix = name_or_value(kwargs['prefix'])
        else:
            prefix = name_or_value(args[offset])
            offset += 1

        # Make sure to sanitize the key as well
        if 'key' in kwargs:
            key = name_or_value(kwargs['key'])
        else:
            key = name_or_value(args[offset])

        # Make sure prefix and key are in the stack
        if prefix not in args[0]._stack or key not in args[0]._stack[prefix]:  # pylint: disable=W0212
            return False

        # Execute the method
        return function(*args, **kwargs)

    return wrapper


class CallbackManager(object):
    """CallbackManager is a global callback system designed to be a single place
    where Pika can manage callbacks and process them. It should be referenced
    by the CallbackManager.instance() method instead of constructing new
    instances of it.

    """
    CALLS = 'calls'
    ARGUMENTS = 'arguments'
    DUPLICATE_WARNING = 'Duplicate callback found for "%s:%s"'
    CALLBACK = 'callback'
    ONE_SHOT = 'one_shot'
    ONLY_CALLER = 'only'

    def __init__(self):
        """Create an instance of the CallbackManager"""
        self._stack = dict()

    @sanitize_prefix
    def add(self,
            prefix,
            key,
            callback,
            one_shot=True,
            only_caller=None,
            arguments=None):
        """Add a callback to the stack for the specified key. If the call is
        specified as one_shot, it will be removed after being fired

        The prefix is usually the channel number but the class is generic
        and prefix and key may be any value. If you pass in only_caller
        CallbackManager will restrict processing of the callback to only
        the calling function/object that you specify.

        :param str|int prefix: Categorize the callback
        :param str|dict key: The key for the callback
        :param callable callback: The callback to call
        :param bool one_shot: Remove this callback after it is called
        :param object only_caller: Only allow one_caller value to call the
                                   event that fires the callback.
        :param dict arguments: Arguments to validate when processing
        :rtype: tuple(prefix, key)

        """
        # Prep the stack
        if prefix not in self._stack:
            self._stack[prefix] = dict()

        if key not in self._stack[prefix]:
            self._stack[prefix][key] = list()

        # Check for a duplicate
        for callback_dict in self._stack[prefix][key]:
            if (callback_dict[self.CALLBACK] == callback and
                    callback_dict[self.ARGUMENTS] == arguments and
                    callback_dict[self.ONLY_CALLER] == only_caller):
                if callback_dict[self.ONE_SHOT] is True:
                    callback_dict[self.CALLS] += 1
                    LOGGER.debug('Incremented callback reference counter: %r',
                                 callback_dict)
                else:
                    LOGGER.warning(self.DUPLICATE_WARNING, prefix, key)
                return prefix, key

        # Create the callback dictionary
        callback_dict = self._callback_dict(callback, one_shot, only_caller,
                                            arguments)
        self._stack[prefix][key].append(callback_dict)
        LOGGER.debug('Added: %r', callback_dict)
        return prefix, key

    def clear(self):
        """Clear all the callbacks if there are any defined."""
        self._stack = dict()
        LOGGER.debug('Callbacks cleared')

    @sanitize_prefix
    def cleanup(self, prefix):
        """Remove all callbacks from the stack by a prefix. Returns True
        if keys were there to be removed

        :param str or int prefix: The prefix for keeping track of callbacks with
        :rtype: bool

        """
        LOGGER.debug('Clearing out %r from the stack', prefix)
        if prefix not in self._stack or not self._stack[prefix]:
            return False
        del self._stack[prefix]
        return True

    @sanitize_prefix
    def pending(self, prefix, key):
        """Return count of callbacks for a given prefix or key or None

        :param str|int prefix: Categorize the callback
        :param object|str|dict key: The key for the callback
        :rtype: None or int

        """
        if not prefix in self._stack or not key in self._stack[prefix]:
            return None
        return len(self._stack[prefix][key])

    @sanitize_prefix
    @check_for_prefix_and_key
    def process(self, prefix, key, caller, *args, **keywords):
        """Run through and process all the callbacks for the specified keys.
        Caller should be specified at all times so that callbacks which
        require a specific function to call CallbackManager.process will
        not be processed.

        :param str|int prefix: Categorize the callback
        :param object|str|int key: The key for the callback
        :param object caller: Who is firing the event
        :param list args: Any optional arguments
        :param dict keywords: Optional keyword arguments
        :rtype: bool

        """
        LOGGER.debug('Processing %s:%s', prefix, key)
        if prefix not in self._stack or key not in self._stack[prefix]:
            return False

        callbacks = list()
        # Check each callback, append it to the list if it should be called
        for callback_dict in list(self._stack[prefix][key]):
            if self._should_process_callback(callback_dict, caller, list(args)):
                callbacks.append(callback_dict[self.CALLBACK])
                if callback_dict[self.ONE_SHOT]:
                    self._use_one_shot_callback(prefix, key, callback_dict)

        # Call each callback
        for callback in callbacks:
            LOGGER.debug('Calling %s for "%s:%s"', callback, prefix, key)
            try:
                callback(*args, **keywords)
            except:
                LOGGER.exception('Calling %s for "%s:%s" failed', callback,
                                 prefix, key)
                raise
        return True

    @sanitize_prefix
    @check_for_prefix_and_key
    def remove(self, prefix, key, callback_value=None, arguments=None):
        """Remove a callback from the stack by prefix, key and optionally
        the callback itself. If you only pass in prefix and key, all
        callbacks for that prefix and key will be removed.

        :param str or int prefix: The prefix for keeping track of callbacks with
        :param str key: The callback key
        :param callable callback_value: The method defined to call on callback
        :param dict arguments: Optional arguments to check
        :rtype: bool

        """
        if callback_value:
            offsets_to_remove = list()
            for offset in xrange(len(self._stack[prefix][key]), 0, -1):
                callback_dict = self._stack[prefix][key][offset - 1]

                if (callback_dict[self.CALLBACK] == callback_value and
                        self._arguments_match(callback_dict, [arguments])):
                    offsets_to_remove.append(offset - 1)

            for offset in offsets_to_remove:
                try:
                    LOGGER.debug('Removing callback #%i: %r', offset,
                                 self._stack[prefix][key][offset])
                    del self._stack[prefix][key][offset]
                except KeyError:
                    pass

        self._cleanup_callback_dict(prefix, key)
        return True

    @sanitize_prefix
    @check_for_prefix_and_key
    def remove_all(self, prefix, key):
        """Remove all callbacks for the specified prefix and key.

        :param str prefix: The prefix for keeping track of callbacks with
        :param str key: The callback key

        """
        del self._stack[prefix][key]
        self._cleanup_callback_dict(prefix, key)

    def _arguments_match(self, callback_dict, args):
        """Validate if the arguments passed in match the expected arguments in
        the callback_dict. We expect this to be a frame passed in to *args for
        process or passed in as a list from remove.

        :param dict callback_dict: The callback dictionary to evaluate against
        :param list args: The arguments passed in as a list

        """
        if callback_dict[self.ARGUMENTS] is None:
            return True
        if not args:
            return False
        if isinstance(args[0], dict):
            return self._dict_arguments_match(args[0],
                                              callback_dict[self.ARGUMENTS])
        return self._obj_arguments_match(
            args[0].method if hasattr(args[0], 'method') else args[0],
            callback_dict[self.ARGUMENTS])

    def _callback_dict(self, callback, one_shot, only_caller, arguments):
        """Return the callback dictionary.

        :param callable callback: The callback to call
        :param bool one_shot: Remove this callback after it is called
        :param object only_caller: Only allow one_caller value to call the
                                   event that fires the callback.
        :rtype: dict

        """
        value = {
            self.CALLBACK: callback,
            self.ONE_SHOT: one_shot,
            self.ONLY_CALLER: only_caller,
            self.ARGUMENTS: arguments
        }
        if one_shot:
            value[self.CALLS] = 1
        return value

    def _cleanup_callback_dict(self, prefix, key=None):
        """Remove empty dict nodes in the callback stack.

        :param str or int prefix: The prefix for keeping track of callbacks with
        :param str key: The callback key

        """
        if key and key in self._stack[prefix] and not self._stack[prefix][key]:
            del self._stack[prefix][key]
        if prefix in self._stack and not self._stack[prefix]:
            del self._stack[prefix]

    @staticmethod
    def _dict_arguments_match(value, expectation):
        """Checks an dict to see if it has attributes that meet the expectation.

        :param dict value: The dict to evaluate
        :param dict expectation: The values to check against
        :rtype: bool

        """
        LOGGER.debug('Comparing %r to %r', value, expectation)
        for key in expectation:
            if value.get(key) != expectation[key]:
                LOGGER.debug('Values in dict do not match for %s', key)
                return False
        return True

    @staticmethod
    def _obj_arguments_match(value, expectation):
        """Checks an object to see if it has attributes that meet the
        expectation.

        :param object value: The object to evaluate
        :param dict expectation: The values to check against
        :rtype: bool

        """
        for key in expectation:
            if not hasattr(value, key):
                LOGGER.debug('%r does not have required attribute: %s',
                             type(value), key)
                return False
            if getattr(value, key) != expectation[key]:
                LOGGER.debug('Values in %s do not match for %s', type(value),
                             key)
                return False
        return True

    def _should_process_callback(self, callback_dict, caller, args):
        """Returns True if the callback should be processed.

        :param dict callback_dict: The callback configuration
        :param object caller: Who is firing the event
        :param list args: Any optional arguments
        :rtype: bool

        """
        if not self._arguments_match(callback_dict, args):
            LOGGER.debug('Arguments do not match for %r, %r', callback_dict,
                         args)
            return False
        return (callback_dict[self.ONLY_CALLER] is None or
                (callback_dict[self.ONLY_CALLER] and
                 callback_dict[self.ONLY_CALLER] == caller))

    def _use_one_shot_callback(self, prefix, key, callback_dict):
        """Process the one-shot callback, decrementing the use counter and
        removing it from the stack if it's now been fully used.

        :param str or int prefix: The prefix for keeping track of callbacks with
        :param str key: The callback key
        :param dict callback_dict: The callback dict to process

        """
        LOGGER.debug('Processing use of oneshot callback')
        callback_dict[self.CALLS] -= 1
        LOGGER.debug('%i registered uses left', callback_dict[self.CALLS])

        if callback_dict[self.CALLS] <= 0:
            self.remove(prefix, key, callback_dict[self.CALLBACK],
                        callback_dict[self.ARGUMENTS])
