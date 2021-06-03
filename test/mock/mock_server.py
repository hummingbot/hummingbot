"""
A mock server class that takes a BaseHTTPRequestHandler
"""


from http.server import BaseHTTPRequestHandler, HTTPServer
from hummingbot.core.mock_api.mock_web_server import get_open_port
from threading import Thread


class MockServer:
    """
    A class to represent a simple API server
    """

    def __init__(self, server_class: BaseHTTPRequestHandler):
        """
        Constructs all the necessary attributes for the server object
        """
        self._ev_loop: None
        self._started: bool = False
        self._stock_responses = []
        self._host = "localhost"
        self._port = get_open_port()
        self._started = False
        self._server = None
        self._server_thread = None
        self._server_class = server_class

    def start(self):
        """
        Start the mock server.
        """
        self._server = HTTPServer((self._host, self._port), self._server_class)
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
