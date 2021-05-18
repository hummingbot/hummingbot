from http.server import BaseHTTPRequestHandler, HTTPServer
from hummingbot.core.mock_api.mock_web_server import get_open_port
import json
import requests
from threading import Thread


class MockEthNodeRequestHandler(BaseHTTPRequestHandler):
    """
    A mock Eth Node that satisfies the simple expectations for testing purposes
    """

    def do_POST(self):
        """
        Return the jsonrpc version. This is expected when running the isConnected method from Web3
        """
        self.send_response(requests.codes.ok)

        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()

        response_content = json.dumps({'jsonrpc': '2.0'})
        self.wfile.write(response_content.encode('utf-8'))
        return


class MockEthNode:
    """
    A class to represent a mock Ethereum node
    """

    def __init__(self):
        """
        Constructs all the necessary attributes for the MockEthNode object
        """
        self._ev_loop: None
        self._started: bool = False
        self._stock_responses = []
        self._host = "localhost"
        self._port = get_open_port()
        self._started = False
        self._server = None
        self._server_thread = None

    def start(self):
        """
        Start the mock server.
        """
        self._server = HTTPServer((self._host, self._port), MockEthNodeRequestHandler)
        self._server_thread = Thread(target=self._server.serve_forever)
        self._server_thread.setDaemon(True)
        self._server_thread.start()

    def stop(self):
        """
        Stop the server by terminating the server thread. Safe to call if start was never called.
        """
        if self._server_thread:
            self._server_thread.terminate()
            self._server_thread.join()
            self._server_thread = None
        self._server.serve_close()
        self._server = None

    @property
    def host(self) -> str:
        """
        Get the host
        """
        return self._host

    @property
    def port(self) -> int:
        """
        Get the port
        """
        return self._port

    @property
    def url(self) -> str:
        """
        Get the full url as you would in a browser
        """
        return "http://" + self._host + ":" + str(self._port)
