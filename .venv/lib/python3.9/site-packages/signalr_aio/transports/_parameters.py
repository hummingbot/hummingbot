#!/usr/bin/python
# -*- coding: utf-8 -*-

# signalr_aio/transports/_parameters.py
# Stanislav Lazarov


from json import dumps
from urllib.parse import urlparse, urlunparse, urlencode
import requests


class WebSocketParameters:
    def __init__(self, connection):
        self.protocol_version = '1.5'
        self.raw_url = self._clean_url(connection.url)
        self.conn_data = self._get_conn_data(connection.hub)
        self.session = connection.session
        self.headers = None
        self.socket_conf = None
        self._negotiate()
        self.socket_url = self._get_socket_url()

    @staticmethod
    def _clean_url(url):
        if url[-1] == '/':
            return url[:-1]
        else:
            return url

    @staticmethod
    def _get_conn_data(hub):
        conn_data = dumps([{'name': hub}])
        return conn_data

    @staticmethod
    def _format_url(url, action, query):
        return '{url}/{action}?{query}'.format(url=url, action=action, query=query)

    def _negotiate(self):
        if self.session is None:
            self.session = requests.Session()
        query = urlencode({
            'connectionData': self.conn_data,
            'clientProtocol': self.protocol_version,
        })
        url = self._format_url(self.raw_url, 'negotiate', query)
        self.headers = dict(self.session.headers)
        request = self.session.get(url)
        self.headers['Cookie'] = self._get_cookie_str(request.cookies)
        self.socket_conf = request.json()

    @staticmethod
    def _get_cookie_str(request):
        return '; '.join([
            '%s=%s' % (name, value)
            for name, value in request.items()
        ])

    def _get_socket_url(self):
        ws_url = self._get_ws_url_from()
        query = urlencode({
            'transport': 'webSockets',
            'connectionToken': self.socket_conf['ConnectionToken'],
            'connectionData': self.conn_data,
            'clientProtocol': self.socket_conf['ProtocolVersion'],
        })

        return self._format_url(ws_url, 'connect', query)

    def _get_ws_url_from(self):
        parsed = urlparse(self.raw_url)
        scheme = 'wss' if parsed.scheme == 'https' else 'ws'
        url_data = (scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)

        return urlunparse(url_data)
