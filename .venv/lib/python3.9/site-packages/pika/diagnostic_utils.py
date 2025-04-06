"""
Diagnostic utilities
"""

import functools
import sys
import traceback


def create_log_exception_decorator(logger):
    """Create a decorator that logs and reraises any exceptions that escape
    the decorated function

    :param logging.Logger logger:
    :returns: the decorator
    :rtype: callable

    Usage example

    import logging

    from pika.diagnostics_utils import create_log_exception_decorator

    _log_exception = create_log_exception_decorator(logging.getLogger(__name__))

    @_log_exception
    def my_func_or_method():
        raise Exception('Oops!')

    """

    def log_exception(func):
        """The decorator returned by the parent function

        :param func: function to be wrapped
        :returns: the function wrapper
        :rtype: callable
        """

        @functools.wraps(func)
        def log_exception_func_wrap(*args, **kwargs):
            """The wrapper function returned by the decorator. Invokes the
            function with the given args/kwargs and returns the function's
            return value. If the function exits with an exception, logs the
            exception traceback and re-raises the

            :param args: positional args passed to wrapped function
            :param kwargs: keyword args passed to wrapped function
            :returns: whatever the wrapped function returns
            :rtype: object
            """
            try:
                return func(*args, **kwargs)
            except:
                logger.exception(
                    'Wrapped func exited with exception. Caller\'s stack:\n%s',
                    ''.join(traceback.format_exception(*sys.exc_info())))
                raise

        return log_exception_func_wrap

    return log_exception
