# pylint: disable=C0111

import logging
import socket
import pika.compat

LOGGER = logging.getLogger(__name__)

_SUPPORTED_TCP_OPTIONS = {}

try:
    _SUPPORTED_TCP_OPTIONS['TCP_USER_TIMEOUT'] = socket.TCP_USER_TIMEOUT
except AttributeError:
    if pika.compat.LINUX_VERSION and pika.compat.LINUX_VERSION >= (2, 6, 37):
        # this is not the timeout value, but the number corresponding
        # to the constant in tcp.h
        # https://github.com/torvalds/linux/blob/master/include/uapi/linux/tcp.h#
        # #define TCP_USER_TIMEOUT	18	/* How long for loss retry before timeout */
        _SUPPORTED_TCP_OPTIONS['TCP_USER_TIMEOUT'] = 18

try:
    _SUPPORTED_TCP_OPTIONS['TCP_KEEPIDLE'] = socket.TCP_KEEPIDLE
    _SUPPORTED_TCP_OPTIONS['TCP_KEEPCNT'] = socket.TCP_KEEPCNT
    _SUPPORTED_TCP_OPTIONS['TCP_KEEPINTVL'] = socket.TCP_KEEPINTVL
except AttributeError:
    pass


def socket_requires_keepalive(tcp_options):
    return ('TCP_KEEPIDLE' in tcp_options or
            'TCP_KEEPCNT' in tcp_options or
            'TCP_KEEPINTVL' in tcp_options)


def set_sock_opts(tcp_options, sock):
    if not tcp_options:
        return

    if socket_requires_keepalive(tcp_options):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    for key, value in tcp_options.items():
        option = _SUPPORTED_TCP_OPTIONS.get(key)
        if option:
            sock.setsockopt(pika.compat.SOL_TCP, option, value)
        else:
            LOGGER.warning('Unsupported TCP option %s:%s', key, value)
