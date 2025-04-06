import concurrent.futures.thread
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from enum import IntEnum
from functools import partial
from typing import Any, Dict

from commlib.compression import CompressionType
from commlib.connection import BaseConnectionParameters
from commlib.msg import ActionMessage, PubSubMessage, RPCMessage
from commlib.utils import gen_random_id, gen_timestamp

actions_logger = None


class GoalStatus(IntEnum):
    """GoalStatus.
    Enumeration of possible goal statuses for an action.

    ACCEPTED: The goal has been accepted and is waiting to be executed.
    EXECUTING: The goal is currently being executed.
    CANCELING: The goal is in the process of being canceled.
    SUCCEEDED: The goal has been successfully executed.
    ABORTED: The goal has been aborted due to an error or failure.
    CANCELED: The goal has been canceled.
    """

    ACCEPTED = 1
    EXECUTING = 2
    CANCELING = 3
    SUCCEDED = 4
    ABORTED = 5
    CANCELED = 6


class _ActionGoalMessage(RPCMessage):
    """_ActionGoalMessage.
    Internal Action Goal (RPC) Message
    """

    class Request(RPCMessage.Request):
        description: str = ""
        goal_data: Dict[str, Any] = {}

    class Response(RPCMessage.Response):
        status: int = 0
        timestamp: int = -1
        goal_id: str = ""

        def __post_init__(self):
            self.timestamp = int(time.time())


class _ActionResultMessage(RPCMessage):
    """_ActionResultMessage.
    Internal Action Result (RPC) Message
    """

    class Request(RPCMessage.Request):
        goal_id: str = ""

    class Response(RPCMessage.Response):
        status: int = 0
        timestamp: int = -1
        result: Dict[str, Any] = {}

        def __post_init__(self):
            self.timestamp = int(time.time())


class _ActionCancelMessage(RPCMessage):
    """_ActionCancelMessage.
    Internal Action Cancel (RPC) Message
    """

    class Request(RPCMessage.Request):
        goal_id: str = ""
        timestamp: int = gen_timestamp()

    class Response(RPCMessage.Response):
        status: int = 0
        timestamp: int = gen_timestamp()
        result: Dict[str, Any]


class _ActionStatusMessage(PubSubMessage):
    """_ActionStatusMessage.
    Internal Action Status Message.
    """

    goal_id: str = ""
    status: int = 0


class _ActionFeedbackMessage(PubSubMessage):
    """_ActionFeedbackMessage.
    Internal Action Feedback Message
    """

    feedback_data: Dict[str, Any]
    goal_id: str = ""


class GoalHandler:
    @classmethod
    def logger(cls) -> logging.Logger:
        global actions_logger
        if actions_logger is None:
            actions_logger = logging.getLogger(__name__)
        return actions_logger

    def __init__(
        self,
        msg_type: ActionMessage,
        status_publisher: callable,
        feedback_publisher: callable,
        on_goal: callable,
        on_cancel: callable):
        """__init__.
        Initializes a GoalHandler instance with the provided parameters.

        Args:
            msg_type (ActionMessage): The type of action message.
            status_publisher (callable): A callable to publish the status of the goal.
            feedback_publisher (callable): A callable to publish feedback for the goal.
            on_goal (callable): A callable to be executed when the goal is started.
            on_cancel (callable): A callable to be executed when the goal is canceled.

        The GoalHandler instance is responsible for managing the execution of an action goal. It sets the initial status, generates a unique ID, and stores the provided data, publishers, and callables. It also creates a ThreadPoolExecutor with a maximum of 2 workers to execute the goal and handle cancellation.
        """

        self._msg_type = msg_type
        self.status = GoalStatus.ACCEPTED
        self.id = gen_random_id()
        self.data = msg_type.Result() if isinstance(msg_type, ActionMessage) else {}
        self._pub_status = status_publisher
        self._pub_feedback = feedback_publisher
        self.result = msg_type.Result() if isinstance(msg_type, ActionMessage) else {}
        self._task = None
        self._on_goal = on_goal
        self._on_cancel = on_cancel
        self._cancel_event = threading.Event()

        self._executor = ThreadPoolExecutor(max_workers=2)

    @property
    def cancel_event(self):
        return self._cancel_event

    def _done_callback(self, future: Future):
        """_done_callback.
        Callback called when the goal has reached a final state
        (succeded/cancel/aborted).

        Args:
            future:
        """
        if future.cancelled() or self._cancel_event.is_set():
            self.set_status(GoalStatus.CANCELED)
        elif future.done():
            self.set_status(GoalStatus.SUCCEDED)
        else:
            print("Whaaaaaat?..")
        res = future.result()
        self.result = res

    def is_finished(self):
        """is_finished.
        Check wheather the current goal has reached a final state.
        """
        if self.status in (
            GoalStatus.SUCCEDED,
            GoalStatus.CANCELED,
            GoalStatus.ABORTED,
        ):
            return True
        else:
            return False

    def start(self):
        """
        Starts the execution of the goal handler.

        This method submits the `_on_goal` callback to the thread pool executor,
        which will execute the goal handler. It also adds a `_done_callback` to
        the submitted task, which will be called when the goal has reached a
        final state (succeeded, canceled, or aborted).
        """

        self._goal_task = self._executor.submit(partial(self._on_goal, self))
        # self._cancel_task = self._executor.submit(self._on_cancel, self)
        self._goal_task.add_done_callback(self._done_callback)

    def cancel(self):
        """
        Cancels the current goal if it is in a state that allows cancellation.

        This method sets the goal status to `GoalStatus.CANCELING`, cancels the
        `_goal_task` that is executing the goal handler, and sets the `_cancel_event`
        to signal that the goal has been canceled. It then waits for the goal task to
        complete and clears the thread pool executor's internal state.

        If the goal is already in a final state (aborted, canceled, succeeded), this
        method simply returns 0 without performing any action.

        Returns:
            int: 1 if the goal was successfully canceled, 0 otherwise.
        """

        if self.status in (
            GoalStatus.ABORTED,
            GoalStatus.CANCELED,
            GoalStatus.CANCELING,
            GoalStatus.SUCCEDED,
        ):
            return 0
        try:
            self.set_status(GoalStatus.CANCELING)
            self._goal_task.cancel()
            self._cancel_event.set()
            _ = self._goal_task.result()
            # self._executor.shutdown(wait=False)
            self._executor._threads.clear()
            concurrent.futures.thread._threads_queues.clear()
        except Exception as exc:
            print(exc)
            return 0
        return 1

    def set_status(self, status: GoalStatus):
        """
        Sets the status of the goal and publishes a status message.

        Args:
            status (GoalStatus): The new status of the goal.

        Raises:
            ValueError: If the provided status is not a valid GoalStatus.

        Returns:
            None
        """

        if status not in GoalStatus:
            raise ValueError("Wrong status code!")
        status = int(status)
        self.status = status
        msg = _ActionStatusMessage(status=status, goal_id=self.id)
        self._pub_status.publish(msg)

    def send_feedback(self, feedback_msg: _ActionFeedbackMessage):
        """
        Publishes a feedback message for the current goal.

        Args:
            feedback_msg (_ActionFeedbackMessage): The feedback message to publish.

        Returns:
            None
        """

        _fb = feedback_msg.model_dump() if self._msg_type is not None else feedback_msg
        msg = _ActionFeedbackMessage(feedback_data=_fb, goal_id=self.id)
        self._pub_feedback.publish(msg)

    def set_result(self, result):
        self.result = result


class BaseActionService:
    @classmethod
    def logger(cls) -> logging.Logger:
        global actions_logger
        if actions_logger is None:
            actions_logger = logging.getLogger(__name__)
        return actions_logger

    def __init__(
        self,
        action_name: str,
        msg_type: ActionMessage = None,
        debug: bool = True,
        compression: CompressionType = CompressionType.NO_COMPRESSION,
        conn_params: BaseConnectionParameters = None,
        on_goal: callable = None,
        on_cancel: callable = None,
        on_getresult: callable = None):
        """__init__.
        Initializes a BaseActionService instance.

        Args:
            action_name (str): The name of the action.
            msg_type (ActionMessage, optional): The type of action message to use.
            debug (bool, optional): Whether to enable debug mode. Defaults to True.
            compression (CompressionType, optional): The type of compression to use. Defaults to CompressionType.NO_COMPRESSION.
            conn_params (BaseConnectionParameters, optional): The connection parameters to use.
            on_goal (callable, optional): A callback function to be called when a goal is received.
            on_cancel (callable, optional): A callback function to be called when a goal is canceled.
            on_getresult (callable, optional): A callback function to be called when a result is requested.

        Attributes:
            _msg_type (ActionMessage): The type of action message to use.
            _debug (bool): Whether debug mode is enabled.
            _compression (CompressionType): The type of compression to use.
            _action_name (str): The name of the action.
            _on_goal (callable): The callback function to be called when a goal is received.
            _on_cancel (callable): The callback function to be called when a goal is canceled.
            _on_getresult (callable): The callback function to be called when a result is requested.
            _conn_params (BaseConnectionParameters): The connection parameters to use.
            _status_topic (str): The topic for publishing status messages.
            _feedback_topic (str): The topic for publishing feedback messages.
            _goal_rpc_uri (str): The URI for the "send_goal" RPC.
            _cancel_rpc_uri (str): The URI for the "cancel_goal" RPC.
            _result_rpc_uri (str): The URI for the "get_result" RPC.
            _feedback_pub (None): The publisher for feedback messages.
            _status_pub (None): The publisher for status messages.
            _goal_rpc (None): The RPC handler for "send_goal" requests.
            _cancel_rpc (None): The RPC handler for "cancel_goal" requests.
            _result_rpc (None): The RPC handler for "get_result" requests.
            _current_goal (None): The current goal being handled.
        """
        self._msg_type = msg_type
        self._debug = debug
        self._compression = compression
        self._action_name = action_name
        self._on_goal = on_goal
        self._on_cancel = on_cancel
        self._on_getresult = on_getresult
        self._conn_params = conn_params

        self._status_topic = f"{self._action_name}.status"
        self._feedback_topic = f"{self._action_name}.feedback"
        self._goal_rpc_uri = f"{self._action_name}.send_goal"
        self._cancel_rpc_uri = f"{self._action_name}.cancel_goal"
        self._result_rpc_uri = f"{self._action_name}.get_result"

        # To be instantiated by the child classes
        self._feedback_pub = None
        self._status_pub = None
        self._goal_rpc = None
        self._cancel_rpc = None
        self._result_rpc = None
        self._current_goal = None

    @property
    def debug(self):
        return self._debug

    @property
    def log(self):
        return self.logger()

    def run(self):
        """
        Start the Action Service RPC handlers.

        This method starts the RPC handlers for sending goals, canceling goals,
        and getting results. It ensures that the Action Service is properly
        running and ready to handle requests.
        """

        if self._goal_rpc is not None:
            self._goal_rpc.run()
        if self._cancel_rpc is not None:
            self._cancel_rpc.run()
        if self._result_rpc is not None:
            self._result_rpc.run()

    def stop(self):
        """
        Stop the Action Service.

        This method stops the RPC handlers for sending goals, canceling goals,
        and getting results. It ensures that the Action Service is properly
        shut down and releases any resources it was using.
        """

        if self._goal_rpc is not None:
            self._goal_rpc.stop()
        if self._cancel_rpc is not None:
            self._cancel_rpc.stop()
        if self._result_rpc is not None:
            self._result_rpc.stop()

    def _handle_send_goal(self, msg: _ActionGoalMessage.Request):
        """_handle_send_goal.

        Args:
            msg (_ActionGoalMessage.Request): Set Goal Request Message
        """
        resp = _ActionGoalMessage.Response()
        if self._current_goal is None:
            self._current_goal = GoalHandler(
                self._msg_type,
                self._status_pub,
                self._feedback_pub,
                self._on_goal,
                self._on_cancel,
            )
            if self._msg_type is not None:
                self._current_goal.data = self._msg_type.Goal(**msg.goal_data)
            else:
                self._current_goal.data = msg.goal_data
        elif self._current_goal.status in (GoalStatus.SUCCEDED,
                                           GoalStatus.CANCELED,
                                           GoalStatus.ABORTED):
            # Final States - Completed Goal Task
            self._current_goal = GoalHandler(
                self._msg_type,
                self._status_pub,
                self._feedback_pub,
                self._on_goal,
                self._on_cancel,
            )
            if self._msg_type is not None:
                self._current_goal.data = self._msg_type.Goal(**msg.goal_data)
            else:
                self._current_goal.data = msg.goal_data
        elif self._current_goal.status == GoalStatus.ACCEPTED:
            pass
        else:
            return resp
        # Execute user-defined callback
        if self._on_goal is not None:
            resp.status = 1
            resp.goal_id = self._current_goal.id
            self._current_goal.start()
        else:
            resp.goal_id = self._current_goal.id
        return resp

    def _handle_cancel_goal(self, msg: _ActionCancelMessage.Request):
        """_handle_cancel_goal.

        Args:
            msg (_ActionCancelMessage.Request): Cancel Request Message
        """
        resp = _ActionCancelMessage.Response()
        _goal_id = msg.goal_id
        if self._current_goal is None:
            return resp
        if self._current_goal.id != _goal_id:
            return resp
        _status = self._current_goal.cancel()
        resp.status = _status
        return resp

    def _handle_get_result(self, msg: _ActionResultMessage.Request):
        """_handle_get_result.

        Args:
            msg (_ActionResultMessage.Request): Result Request Message
        """
        resp = _ActionResultMessage.Response()
        _goal_id = msg.goal_id
        if _goal_id == "":
            pass
        elif self._current_goal is None:
            return resp
        elif self._current_goal.id != _goal_id:
            return resp
        resp.status = self._current_goal.status
        # Set Result data
        if self._msg_type is not None:
            resp.result = self._current_goal.result.dict()
        else:
            resp.result = self._current_goal.result
        return resp

    def __del__(self):
        self.stop()


class BaseActionClient:
    @classmethod
    def logger(cls) -> logging.Logger:
        global actions_logger
        if actions_logger is None:
            actions_logger = logging.getLogger(__name__)
        return actions_logger

    def __init__(
        self,
        action_name: str,
        msg_type: ActionMessage = None,
        debug: bool = False,
        compression: CompressionType = CompressionType.NO_COMPRESSION,
        conn_params: BaseConnectionParameters = None,
        on_feedback: callable = None,
        on_result: callable = None,
        on_goal_reached: callable = None):
        """
        Initializes an instance of the `BaseActionClient` class.

        Args:
            action_name (str): The name of the action.
            msg_type (ActionMessage, optional): The type of the action message.
            debug (bool, optional): Whether to enable debug mode.
            compression (CompressionType, optional): The type of compression to use.
            conn_params (BaseConnectionParameters, optional): The connection parameters.
            on_feedback (callable, optional): A callback function for handling feedback.
            on_result (callable, optional): A callback function for handling results.
            on_goal_reached (callable, optional): A callback function for handling when a goal is reached.
        """

        self._debug = debug
        self._action_name = action_name
        self._msg_type = msg_type
        self._compression = compression
        self._conn_params = conn_params

        self._status_topic = f"{self._action_name}.status"
        self._feedback_topic = f"{self._action_name}.feedback"
        self._goal_rpc_uri = f"{self._action_name}.send_goal"
        self._cancel_rpc_uri = f"{self._action_name}.cancel_goal"
        self._result_rpc_uri = f"{self._action_name}.get_result"

        # To be instantiated by the child classes
        self._goal_client = None
        self._cancel_client = None
        self._result_client = None
        self._status_sub = None
        self._feedback_sub = None
        self._goal_id = None

        self._status = _ActionStatusMessage()
        self.on_feedback = on_feedback
        self.result = None
        self.on_result = on_result
        self.on_goal_reached = on_goal_reached

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def log(self):
        return self.logger()

    def send_goal(
        self,
        goal_msg: ActionMessage.Goal,
        timeout: int = 10,
        wait_for_result: bool = False) -> _ActionGoalMessage.Response:
        """send_goal.
        Send a new goal to the Action service.

        Args:
            goal_msg (ActionMessage.Goal): The Action Goal Message
            timeout (int): timeout
            wait_for_result (bool): Weather to wait for result or not.

        Returns:
            _ActionGoalMessage.Response:
        """
        _data = {}
        if isinstance(goal_msg, dict) or isinstance(goal_msg, Dict):
            _data = goal_msg
        elif isinstance(goal_msg, ActionMessage.Goal):
            _data = goal_msg.dict()
        req = _ActionGoalMessage.Request(goal_data=_data)
        self._status = _ActionStatusMessage()
        resp = self._goal_client.call(req, timeout=timeout)
        self.result = None
        self._goal_id = resp.goal_id
        return resp

    def cancel_goal(self,
                    timeout: float = 10.0,
                    wait_for_result: bool = False
                    ) -> _ActionCancelMessage.Response:
        """cancel_goal.
        Cancel the current goal.

        Args:
            timeout (float): timeout
            wait_for_result (bool): Weather to wait for result or not.

        Returns:
            _ActionCancelMessage.Response:
        """
        req = _ActionCancelMessage.Request(goal_id=self._goal_id)
        _ = self._cancel_client.call(req, timeout=timeout)
        # TODO Check response status
        res = self.get_result(wait=wait_for_result)
        return res

    def get_result(self,
                   timeout: float = 10.0,
                   wait: bool = False,
                   wait_max_sec: float = 30.0
                   ) -> ActionMessage.Result:
        """get_result.
        Returns the result of the goal.

        Args:
            timeout (float): timeout
            wait (bool): Wait for the goal to finish if result does not exist.
            wait_max_sec (float): Maximum time to wait for result if `wait`
                is set to True.

        Returns:
            ActionMessage.Result:
        """
        if self.result is not None:
            return self.result
        req = _ActionResultMessage.Request(goal_id=self._goal_id)
        if wait:
            t_start = time.time()
            t_elapsed = 0
            while t_elapsed < wait_max_sec:
                # If the goal has reached a final state
                if self._status.status in (
                    GoalStatus.ABORTED,
                    GoalStatus.SUCCEDED,
                    GoalStatus.CANCELED,
                ):
                    resp = self._result_client.call(req, timeout=timeout)
                    if self._msg_type is None:
                        res = resp.result
                    else:
                        res = self._msg_type.Result(**resp.result)
                    self.result = res
                    return res
                time.sleep(0.001)
                t_elapsed = time.time() - t_start
        return None

    def _on_status(self, msg: _ActionStatusMessage) -> None:
        """_on_status.
        Internal on_status event callback.

        Args:
            msg (_ActionStatusMessage): Action status message (Internal use)

        Returns:
            None:
        """
        # Check if the goal_id matches the one of the current goal.
        if msg.goal_id != self._goal_id:
            return
        self._status = msg
        # If it reaches a final state F
        if self._status.status in (
            GoalStatus.SUCCEDED,
            GoalStatus.CANCELED,
            GoalStatus.ABORTED,
        ):
            res = self.get_result(wait=True, wait_max_sec=10)
            self.result = res
            # Call the on_goal_reached callback
            if (
                self._status.status == GoalStatus.SUCCEDED
                and self.on_goal_reached is not None
            ):
                self.on_goal_reached(res)

            # If the on_result callback was declared
            if self.on_result is not None:
                self.on_result(res)

    def _on_feedback(self, msg: _ActionFeedbackMessage) -> None:
        """_on_feedback.
        Internal on_feedback event callback.

        Args:
            msg (_ActionFeedbackMessage): Action feedback Message
                (Internal use)

        Returns:
            None:
        """
        # Check if the goal_id matches the one of the current goal.
        if msg.goal_id != self._goal_id:
            return
        fb = (
            self._msg_type.Feedback(**msg.feedback_data)
            if self._msg_type is not None
            else msg.feedback_data
        )
        if self.on_feedback is not None:
            self.on_feedback(fb)

    def run(self):
        """
        Run the action client endpoints.

        This method starts the execution of the action client endpoints, including the status subscriber, feedback subscriber, goal client, cancel client, and result client. These endpoints are responsible for communicating with the action server and handling the various stages of the action execution.
        """

        self._status_sub.run()
        self._feedback_sub.run()
        self._goal_client.run()
        self._cancel_client.run()
        self._result_client.run()

    def stop(self) -> None:
        """stop.
        Stop action client endpoints.

        Args:

        Returns:
            None:
        """
        if self._status_sub is not None:
            self._status_sub.stop()
        if self._feedback_sub is not None:
            self._feedback_sub.stop()
        if self._goal_client is not None:
            self._goal_client.stop()
        if self._cancel_client is not None:
            self._cancel_client.stop()
        if self._result_client is not None:
            self._result_client.stop()

    def __del__(self):
        self.stop()
