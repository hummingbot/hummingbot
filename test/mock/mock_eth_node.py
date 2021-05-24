"""
Mock server implementation for an Ethereum Node
"""

from test.mock.mock_server import PingableHttpRequestHandler
import json
import requests


class MockEthNodeRequestHandler(PingableHttpRequestHandler):
    """
    A mock Eth Node that satisfies the simple expectations for testing purposes
    """

    def do_POST(self):
        """
        Return the jsonrpc version. This is expected when running the isConnected method from Web3.
        """
        self.send_response(requests.codes.ok)

        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()

        response_content = json.dumps({'jsonrpc': '2.0'})
        self.wfile.write(response_content.encode('utf-8'))
        return
