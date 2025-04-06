from pydantic import BaseModel


class AuthBase(BaseModel):
    pass


class AuthPlain(AuthBase):
    username: str
    password: str


class BaseConnectionParameters(BaseModel):
    """
    Defines the common connection parameters across protocol transports (MQTT, AMQP, etc.).

    :param host: The hostname or IP address of the connection endpoint.
    :param port: The port number of the connection endpoint.
    :param ssl: Whether to use SSL/TLS encryption for the connection.
    :param ssl_insecure: Whether to allow insecure SSL/TLS connections (e.g. self-signed certificates).
    :param reconnect_attempts: The number of times to attempt reconnecting if the connection is lost.
    :param reconnect_delay: The delay in seconds between reconnect attempts.
    """

    host: str
    port: int
    ssl: bool = False
    ssl_insecure: bool = False
    reconnect_attempts: int = 5
    reconnect_delay: float = 5.0
