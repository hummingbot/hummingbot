import socket
import socketserver


class TCPBridgeRequestHandler(socketserver.BaseRequestHandler):
    """
    TCP Proxy Server
    Instantiated once time for each connection, and must
    override the handle() method for client communication.
    """

    def handle(self):
        """
        Handles a TCP connection by forwarding data between the client and a remote server.

        This method is called for each incoming TCP connection. It receives the client data,
        forwards it to the remote server, and then forwards any response data from the
        remote server back to the client.

        Args:
            self (TCPBridgeRequestHandler): The request handler instance.

        Raises:
            Exception: If there is an error connecting to or communicating with the remote server.
        """

        # self.request is the TCP socket connected to the client
        data = self.request.recv(1024)
        print("Passing data from: {}".format(self.client_address[0]))
        print(data)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Try to connect to the server and send data
            try:
                sock.connect((self.server.host_ep2, self.server.port_ep2))
                sock.sendall(data)
                # Receive data from the server
                while True:
                    received = sock.recv(1024)
                    if not received:
                        break
                    # Send back received data
                    self.request.sendall(received)
            except Exception as exc:
                print(exc)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    A threaded TCP server that handles each client connection in a separate thread.
    """

    pass


class TCPBridge(ThreadedTCPServer):

    def __init__(self, host_ep1: str, port_ep1: int, host_ep2: str, port_ep2: int):
        """__init__.
        Initializes a TCPBridge instance with the specified host and port for both endpoints.

        Args:
            host_ep1 (str): The host address for the first endpoint.
            port_ep1 (int): The port number for the first endpoint.
            host_ep2 (str): The host address for the second endpoint.
            port_ep2 (int): The port number for the second endpoint.
        """

        self.host_ep1 = host_ep1
        self.host_ep2 = host_ep2
        self.port_ep1 = port_ep1
        self.port_ep2 = port_ep2
        super().__init__((host_ep1, port_ep1), TCPBridgeRequestHandler)
