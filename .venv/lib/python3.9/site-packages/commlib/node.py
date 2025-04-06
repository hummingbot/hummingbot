import logging
import threading
import time
from enum import IntEnum
from typing import Any, List, Optional
from pydantic import BaseModel

from commlib.compression import CompressionType
from commlib.msg import HeartbeatMessage, RPCMessage
from commlib.pubsub import BasePublisher
from commlib.utils import gen_random_id
from concurrent.futures import ThreadPoolExecutor

n_logger: logging.Logger = None


class NodePort(BaseModel):
    endpoints: List[Any] = []


class NodePorts(BaseModel):
    input: List[NodePort] = []
    output: List[NodePort] = []


class NodePortType(IntEnum):
    """NodePortType."""

    Input = 1
    Output = 2


class NodeExecutorType(IntEnum):
    """NodeExecutorType."""

    ProcessExecutor = 1
    ThreadExecutor = 2


class NodeState(IntEnum):
    IDLE = 1
    RUNNING = 2
    STOPPED = 4
    EXITED = 3


class HeartbeatThread:
    @classmethod
    def logger(cls) -> logging.Logger:
        global n_logger
        if n_logger is None:
            n_logger = logging.getLogger(__name__)
        return n_logger

    def __init__(
        self,
        pub_instance: BasePublisher,
        interval: Optional[float] = 10,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self._rate_secs = interval
        self._heartbeat_pub = pub_instance

    def start(self):
        """start"""
        try:
            msg = HeartbeatMessage(ts=self.get_ts())
            while self.running():
                self.logger().debug(
                    f"Sending heartbeat message - {self._heartbeat_pub._topic}"
                )
                if self._heartbeat_pub._msg_type is None:
                    self._heartbeat_pub.publish(msg.model_dump())
                else:
                    self._heartbeat_pub.publish(msg)
                # Wait for n seconds or until stop event is raised
                self._stop_event.wait(self._rate_secs)
                msg.ts = self.get_ts()
            self.logger().debug("Heartbeat Thread Ended")
        except Exception as exc:
            self.logger().error(f"Exception in Heartbeat-Thread: {exc}")

    def stop(self):
        """stop."""
        self._stop_event.set()

    def running(self):
        """stopped."""
        return not self._stop_event.is_set()

    def get_ts(self):
        """get_ts."""
        timestamp = (time.time() + 0.5) * 1000000
        return int(timestamp)


class _NodeStartMessage(RPCMessage):
    class Request(RPCMessage.Request):
        pass

    class Response(RPCMessage.Response):
        status: int = 0
        error: str = ""


class _NodeStopMessage(RPCMessage):
    class Request(RPCMessage.Request):
        pass

    class Response(RPCMessage.Response):
        status: int = 0
        error: str = ""


class Node:
    """Node."""

    @classmethod
    def logger(cls) -> logging.Logger:
        global n_logger
        if n_logger is None:
            n_logger = logging.getLogger(__name__)
        return n_logger

    def __init__(
        self,
        node_name: Optional[str] = "",
        connection_params: Optional[Any] = None,
        transport_connection_params: Optional[Any] = None,
        debug: Optional[bool] = False,
        heartbeats: Optional[bool] = True,
        heartbeat_interval: Optional[float] = 10.0,
        heartbeat_uri: Optional[str] = None,
        compression: CompressionType = CompressionType.NO_COMPRESSION,
        ctrl_services: Optional[bool] = False,
        workers_rpc: Optional[int] = 5,
    ):
        """__init__.

        Args:
            node_name (Optional[str]): node_name
            transport_type (Optional[TransportType]): transport_type
            connection_params (Optional[Any]): connection_params
            transport_connection_params (Optional[Any]): Same with connection_params.
                Used for backward compatibility
            debug (Optional[bool]): debug
            heartbeats (Optional[bool]): heartbeat_thread
            heartbeat_interval (Optional[float]): Heartbeat publishing interval
                in seconds
            heartbeat_uri (Optional[str]): The Topic URI to publish heartbeat
                messages
            ctrl_services (Optional[bool]): Enable/Disable control interfaces
        """
        if node_name == "" or node_name is None:
            node_name = gen_random_id()
        node_name = node_name.replace("-", "_")
        self._node_name = node_name
        self._debug = debug
        self._hb_thread = None
        self._workers_rpc = workers_rpc
        self._namespace = self._node_name
        self._has_ctrl_services = ctrl_services
        self._heartbeats = heartbeats
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_uri = (
            heartbeat_uri
            if heartbeat_uri is not None
            else f"{self._namespace}.heartbeat"
        )
        self._compression = compression
        self.state = NodeState.IDLE

        self._publishers = []
        self._subscribers = []
        self._rpc_services = []
        self._rpc_clients = []
        self._action_services = []
        self._action_clients = []
        self._event_emitters = []
        self._ports: List[NodePort] = []
        self._executor = ThreadPoolExecutor()
        self._workers: List[Any] = []

        # Set default ConnectionParameters ---->
        if transport_connection_params is not None and connection_params is None:
            connection_params = transport_connection_params
        self._conn_params = connection_params
        self._select_transport()

    def _select_transport(self):
        type_str = str(type(self._conn_params)).split("'")[1]

        if type_str == "commlib.transports.mqtt.ConnectionParameters":
            import commlib.transports.mqtt as transport_module
        elif type_str == "commlib.transports.redis.ConnectionParameters":
            import commlib.transports.redis as transport_module
        elif type_str == "commlib.transports.amqp.ConnectionParameters":
            import commlib.transports.amqp as transport_module
        elif type_str == "commlib.transports.kafka.ConnectionParameters":
            import commlib.transports.kafka as transport_module
        elif type_str == "commlib.transports.mock.ConnectionParameters":
            import commlib.transports.mock as transport_module
        else:
            raise ValueError("Transport type is not supported!")
        self._transport_module = transport_module

    @property
    def log(self) -> logging.Logger:
        return self.logger()

    def _init_heartbeat_thread(self) -> None:
        hb_pub = self.create_publisher(
            topic=self._heartbeat_uri, msg_type=HeartbeatMessage
        )
        hb_pub.run()
        self._hb_thread = HeartbeatThread(hb_pub, interval=self._heartbeat_interval)
        work = self._executor.submit(self._hb_thread.start).add_done_callback(
            Node._worker_clb
        )
        self._workers.append(work)

    @staticmethod
    def _worker_clb(f):
        e = f.exception()
        if e is None:
            return
        trace = []
        tb = e.__traceback__
        while tb is not None:
            trace.append(
                {
                    "filename": tb.tb_frame.f_code.co_filename,
                    "name": tb.tb_frame.f_code.co_name,
                    "lineno": tb.tb_lineno,
                }
            )
            tb = tb.tb_next
        print(str({"type": type(e).__name__, "message": str(e), "trace": trace}))

    def create_stop_service(self, uri: str = "") -> None:
        if uri in (None, ""):
            uri = f"{self._namespace}.stop"
        self.create_rpc(
            rpc_name=uri, msg_type=_NodeStopMessage, on_request=self._stop_rpc_callback
        )

    def _stop_rpc_callback(
        self, msg: _NodeStopMessage.Request
    ) -> _NodeStopMessage.Response:
        resp = _NodeStopMessage.Response()
        if self.state == NodeState.RUNNING:
            self.state = NodeState.STOPPED
            self.stop()
        else:
            resp.status = 1
            resp.error = "Cannot make the transition from current state!"
        return resp

    def create_start_service(self, uri: str = "") -> None:
        if uri in ("", None):
            uri = f"{self._namespace}.start"
        self.create_rpc(
            rpc_name=uri,
            msg_type=_NodeStartMessage,
            on_request=self._start_rpc_callback,
        )

    def _start_rpc_callback(
        self, msg: _NodeStartMessage.Request
    ) -> _NodeStartMessage.Response:
        resp = _NodeStartMessage.Response()
        if self.state == NodeState.STOPPED:
            self.run()
        else:
            resp.status = 1
            resp.error = "Cannot make the transition from current state!"
        return resp

    @property
    def input_ports(self) -> dict:
        return {
            "subscriber": self._subscribers,
            "rpc_service": self._rpc_services,
            "action_service": self._action_services,
        }

    @property
    def output_ports(self):
        return {
            "publisher": self._publishers,
            "rpc_client": self._rpc_clients,
            "action_client": self._action_clients,
        }

    @property
    def ports(self):
        return {"input": self.input_ports, "output": self.output_ports}

    def run(self) -> None:
        """run
        Starts the node by running all its subscribers, publishers, RPC services, RPC clients, action services, and action clients. If the node has control services, it also creates the start and stop services. If the node has heartbeats, it initializes the heartbeat thread. Finally, it sets the node state to RUNNING.
        """

        self.log.info(f"Starting Node <{self._node_name}>")
        if self._has_ctrl_services:
            self.create_start_service()
            self.create_stop_service()
        for c in self._subscribers:
            c.run()
        for c in self._publishers:
            c.run()
        for c in self._rpc_services:
            c.run()
        for c in self._rpc_clients:
            c.run()
        for c in self._action_services:
            c.run()
        for c in self._action_clients:
            c.run()
        if self._heartbeats:
            self._init_heartbeat_thread()
        self.state = NodeState.RUNNING

    def run_forever(self, sleep_rate: float = 0.01) -> None:
        """run_forever
        Runs the node indefinitely until the node state is set to EXITED.
        This method first checks if the node is in the RUNNING state, and if not,
        it calls the `run()` method to start the node. It then enters a loop that
        sleeps for the specified `sleep_rate` (default is 0.01 seconds) until the
        node state is set to EXITED. If an exception occurs during the loop,
        it is caught and ignored.

        Finally, the `stop()` method is called to stop the node.

        Args:
            sleep_rate (float): Rate to sleep between wait-state iterations.
        """

        if self.state != NodeState.RUNNING:
            self.run()
        try:
            while self.state != NodeState.EXITED:
                time.sleep(sleep_rate)
        except:
            pass
        self.stop()

    def stop(self):
        """stop
        Stops the node by stopping all its subscribers, publishers, RPC services,
        RPC clients, action services, and action clients. If the node has a
        heartbeat thread, it is also stopped. If the node has an executor,
        it is shut down. Finally, the node state is set to EXITED.
        """

        for c in self._subscribers:
            c.stop()
        for c in self._publishers:
            c.stop()
        for c in self._rpc_services:
            c.stop()
        for c in self._rpc_clients:
            c.stop()
        for c in self._action_services:
            c.stop()
        for c in self._action_clients:
            c.stop()
        if self._hb_thread:
            self._hb_thread.stop()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        self.state = NodeState.EXITED

    def create_publisher(self, *args, **kwargs):
        """create_publisher
        Creates a new Publisher Endpoint.

        Args:
            *args: Positional arguments to be passed to the Publisher constructor.
            **kwargs: Keyword arguments to be passed to the Publisher constructor.

        Returns:
            The created Publisher instance.
        """

        pub = self._transport_module.Publisher(
            conn_params=self._conn_params,
            compression=self._compression,
            *args,
            **kwargs,
        )
        self._publishers.append(pub)
        return pub

    def create_mpublisher(self, *args, **kwargs):
        """create_mpublisher
        Creates a new MPublisher (Multi-Topic Publisher) Endpoint.

        Args:
            *args: Positional arguments to be passed to the MPublisher constructor.
            **kwargs: Keyword arguments to be passed to the MPublisher constructor.

        Returns:
            The created MPublisher instance.
        """

        pub = self._transport_module.MPublisher(
            conn_params=self._conn_params,
            compression=self._compression,
            *args,
            **kwargs,
        )
        self._publishers.append(pub)
        return pub

    def create_subscriber(self, *args, **kwargs):
        """create_subscriber
        Creates a new Subscriber Endpoint.

        Args:
            *args: Positional arguments to be passed to the Subscriber constructor.
            **kwargs: Keyword arguments to be passed to the Subscriber constructor.

        Returns:
            The created Subscriber instance.
        """

        sub = self._transport_module.Subscriber(
            conn_params=self._conn_params,
            compression=self._compression,
            *args,
            **kwargs,
        )
        self._subscribers.append(sub)
        return sub

    def create_psubscriber(self, *args, **kwargs):
        """create_psubscriber
        Creates a new PSubscriber Endpoint.

        Args:
            *args: Positional arguments to be passed to the PSubscriber constructor.
            **kwargs: Keyword arguments to be passed to the PSubscriber constructor.

        Returns:
            The created PSubscriber instance.
        """

        sub = self._transport_module.PSubscriber(
            conn_params=self._conn_params,
            compression=self._compression,
            *args,
            **kwargs,
        )
        self._subscribers.append(sub)
        return sub

    def create_rpc(self, *args, **kwargs):
        """create_rpc.
        Creates a new RPCService Endpoint.

        Args:
            *args: Positional arguments to be passed to the RPCService constructor.
            **kwargs: Keyword arguments to be passed to the RPCService constructor.

        Returns:
            The created RPCService instance.
        """

        rpc = self._transport_module.RPCService(
            conn_params=self._conn_params,
            compression=self._compression,
            workers=self._workers_rpc,
            *args,
            **kwargs,
        )
        self._rpc_services.append(rpc)
        return rpc

    def create_rpc_client(self, *args, **kwargs):
        """create_rpc_client.
        Creates a new RPCClient Endpoint.

        Args:
            *args: Positional arguments to be passed to the RPCClient constructor.
            **kwargs: Keyword arguments to be passed to the RPCClient constructor.

        Returns:
            The created RPCClient instance.
        """

        client = self._transport_module.RPCClient(
            conn_params=self._conn_params,
            compression=self._compression,
            *args,
            **kwargs,
        )
        self._rpc_clients.append(client)
        return client

    def create_action(self, *args, **kwargs):
        """create_action.
        Creates a new ActionService Endpoint.

        Args:
            *args: Positional arguments to be passed to the ActionService constructor.
            **kwargs: Keyword arguments to be passed to the ActionService constructor.

        Returns:
            The created ActionService instance.
        """

        action = self._transport_module.ActionService(
            conn_params=self._conn_params,
            compression=self._compression,
            *args,
            **kwargs,
        )
        self._action_services.append(action)
        return action

    def create_action_client(self, *args, **kwargs):
        """create_action_client.
        Creates a new ActionClient Endpoint.

        Args:
            *args: Positional arguments to be passed to the ActionClient constructor.
            **kwargs: Keyword arguments to be passed to the ActionClient constructor.

        Returns:
            The created ActionClient instance.
        """

        aclient = self._transport_module.ActionClient(
            conn_params=self._conn_params,
            compression=self._compression,
            *args,
            **kwargs,
        )
        self._action_clients.append(aclient)
        return aclient

    def subscribe(self, topic, msg_type):
        """subscribe.
        Decorator to create a new Subscriber Endpoint.

        Args:
            topic (str): The topic to subscribe to.
            msg_type (type): The message type expected for the subscription.

        Returns:
            A decorator function that, when applied to a function, creates a new Subscriber Endpoint using the provided function as the message handler.
        """

        def wrapper(func):
            _ = self.create_subscriber(
                on_message=func,
                msg_type=msg_type,
                topic=topic
            )
            return func

        return wrapper

    def rpc(self, rpc_name, msg_type):
        """rpc.
        Decorator to create a new RPC service endpoint.

        Args:
            rpc_name (str): The name of the RPC service.
            msg_type (type): The message type expected for the RPC service.

        Returns:
            A decorator function that, when applied to a function, creates a new RPC service endpoint using the provided function as the request handler.
        """

        def wrapper(func):
            _ = self.create_rpc(
                on_request=func,
                msg_type=msg_type,
                rpc_name=rpc_name
            )
            return func

        return wrapper
