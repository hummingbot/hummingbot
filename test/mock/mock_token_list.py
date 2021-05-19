"""
Mock server implementation for an API that returns a list of tokens
"""

from http.server import BaseHTTPRequestHandler
import json
import requests


class MockTokenListRequestHandler(BaseHTTPRequestHandler):
    """
    A mock token listing API
    """

    def do_GET(self):
        """
        Return token symbols
        """
        self.send_response(requests.codes.ok)

        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()

        response_content = json.dumps({'tokens': [{"symbol": "ETH"}, {"symbol": "DAI"}, {"symbol": "BTC"}]})
        self.wfile.write(response_content.encode('utf-8'))
        return
