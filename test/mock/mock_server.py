"""
A mock server class that takes a BaseHTTPRequestHandler
"""

from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
from hummingbot.core.mock_api.mock_web_server import get_open_port
from threading import Thread


class PingableHttpRequestHandler(BaseHTTPRequestHandler):
    """
    A simple server with a route "/ping" predefined. This is useful for blocking until the server is available.
    """

    def do_PING(self):
        self.send_response(200)
        self.end_headers()


class StoppableHTTPServer(HTTPServer):
    """
    An http server that is stoppable, it is not straightforward to stop the original implementation
    """

    def __init__(self, server_address, RequestHandlerClass):
        HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.stop = False

    def serve_forever(self):
        """Handle one request at a time until stopped."""
        self.stop = False
        while not self.stop:
            self.handle_request()

    def stop_server(self):
        self.stop = True


class MockServer:
    """
    A class to represent a simple API server
    """

    def __init__(self, server_class: PingableHttpRequestHandler):
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

    def __enter__(self):
        """
        with MockServer() as mock_server
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        stop server when using with
        """
        self.stop()

    def ping(self):
        """
        The mock server we create is an instance of PingableHttpRequestHandler, this implements a ping route that
        should return 200 when it is reachable. When starting the MockServer, we block until the server is reachable.
        """
        conn = HTTPConnection("localhost:%d" % self._port)
        conn.request("PING", "/ping")
        return conn.getresponse().status == 200

    def start(self):
        """
        Manually start the mock server.
        """
        self._server = StoppableHTTPServer((self._host, self._port), self._server_class)
        self._server_thread = Thread(target=self._server.serve_forever)
        self._server_thread.setDaemon(True)
        self._server_thread.start()

        # block until able to ping the internal server
        successfully_pinged = False
        while not successfully_pinged:
            successfully_pinged = self.ping()

    def stop(self):
        """
        Manually stop the server by terminating the server thread. Safe to call if start was never called.
        """
        if self._server:
            self._server.stop()

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
