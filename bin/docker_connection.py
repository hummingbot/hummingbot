import aioprocessing
import asyncio
import docker
import logging
from multiprocessing import Process
import types
from typing import Callable, Dict, Any, List, Generator, Union, Optional, AsyncIterable

logger: logging.Logger = logging.getLogger(__name__)
global_hummingbot_pipe: Optional[aioprocessing.AioConnection] = None

GATEWAY_DOCKER_REPO: str = "coinalpha/gateway-v2-dev"
GATEWAY_DOCKER_TAG: str = "20220131"


async def _start_docker_controller(docker_pipe: aioprocessing.AioConnection):
    """
    Run the docker controller loop.

    Note that all the I/O operations must be converted to asynchronous operations. This allows any operations within
    this loop to be cancellable when the user desires to exit. Having any blocking I/O operation in this loop would mean
    the potential for the child process to be stuck while the user is trying to exit from Hummingbot.
    """
    docker_client: docker.APIClient = docker.APIClient(base_url="unix://var/run/docker.sock")
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    while True:
        try:
            method_name: str
            method_args: List[Any]
            method_kwargs: Dict[str, Any]
            method_name, method_args, method_kwargs = await docker_pipe.coro_recv()
        except EOFError:
            # Exit gracefully, if the pipe is closed on the hummingbot side.
            return
        except Exception:
            logging.error("Error parsing docker IPC commands from main process.", exc_info=True)
            await asyncio.sleep(0.5)
            continue

        try:
            method: Callable = getattr(docker_client, method_name)
            response: Union[str, Generator[str, None, None]] = await ev_loop.run_in_executor(
                None,
                lambda: method(*method_args, **method_kwargs)
            )

            if isinstance(response, types.GeneratorType):
                for data in response:
                    await docker_pipe.coro_send(data)
                await docker_pipe.coro_send(None)
            else:
                await docker_pipe.coro_send(response)
        except Exception as e:
            await docker_pipe.coro_send(e)


async def _watch_for_terminate_event(terminate_evt: aioprocessing.AioEvent):
    """
    Watches for the terminate event from the main process, and terminate all running background tasks to cause the
    docker controller process to exit gracefully.
    """
    await terminate_evt.coro_wait()
    for task in asyncio.all_tasks():
        task.cancel()


def _docker_process_main(
        hummingbot_pipe: aioprocessing.AioConnection,
        docker_pipe: aioprocessing.AioConnection,
        terminate_evt: aioprocessing.AioEvent
):
    """
    Starts the docker controller loop and the terminate event watcher.

    Note that terminate event watcher is needed even though the docker controller loop would usually terminate when the
    hummingbot side of the pipe is closed. This is because there are some cases where the controller loop may not be
    able to exit by itself quickly. Consider the following case:

     1. User types `gateway create`, which pulls in a gateway image, which may take a long time.
     2. User then tries to exit with Ctrl-C Ctrl-C.

    In the absence of the terminate event watcher, the docker controller loop can only exit after the docker pull action
    has finished - because it can only discover the pipe is closed on the next iteration. With the terminate event
    watcher, the controller loop is cancelled immediately, and the docker controller process would be able to exit
    immediately.
    """
    # Set up the event loop for the new process.
    ev_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    asyncio.set_event_loop(ev_loop)

    # Close the hummingbot pipe on the child process, s.t. only the main process will own it.
    hummingbot_pipe.close()

    # Start the docker controller loop and the terminate event monitor in parallel.
    try:
        ev_loop.run_until_complete(asyncio.gather(
            _start_docker_controller(docker_pipe),
            _watch_for_terminate_event(terminate_evt)
        ))
    except asyncio.CancelledError:
        return


def fork_and_start(main_function: Callable):
    """
    Forks a child process to run as the docker controller, and keep running the `main_function()` as the main process.

    When the `main_function()` exits, the child process is notified via `terminate_evt`, which will cause the child
    process to exit immediately as well. Afterwards, call join() and close() on the child process to ensure all acquired
    resources are freed up.
    """
    p1, p2 = aioprocessing.AioPipe()
    terminate_evt: aioprocessing.AioEvent = aioprocessing.AioEvent()
    docker_process: Process = Process(target=_docker_process_main,
                                      args=(p1, p2, terminate_evt))

    try:
        # fork the docker process as child.
        docker_process.start()

        # run the main function as parent.
        global global_hummingbot_pipe
        global_hummingbot_pipe = p1
        main_function()

        # stop the gateway container.
        try:
            asyncio.get_event_loop().run_until_complete(docker_ipc(
                "stop",
                container=get_gateway_container_name(),
                timeout=1
            ))
        except Exception:
            pass
    finally:

        # close pipes.
        p1.close()
        p2.close()

        # set the terminate event.
        terminate_evt.set()

        # wait for Docker controller process to clean up.
        docker_process.join()
        docker_process.close()


def get_gateway_container_name() -> str:
    from hummingbot.client.config.global_config_map import global_config_map
    instance_id_suffix: str = global_config_map["instance_id"].value[:8]
    return f"hummingbot-gateway-{instance_id_suffix}"


async def docker_ipc(method_name: str, *args, **kwargs) -> Any:
    from hummingbot.client.hummingbot_application import HummingbotApplication
    global global_hummingbot_pipe

    if global_hummingbot_pipe is None:
        raise RuntimeError("Not in the main process, or hummingbot wasn't started via `fork_and_start()`.")
    try:
        global_hummingbot_pipe.send((method_name, args, kwargs))
        return await global_hummingbot_pipe.coro_recv()
    except Exception as e:  # unable to communicate with docker socket
        HummingbotApplication.main_application().notify(
            "\nError: Unable to communicate with docker socket. "
            "\nEnsure dockerd is running and /var/run/docker.sock exists, then restart Hummingbot.")
        raise e


async def docker_ipc_with_generator(method_name: str, *args, **kwargs) -> AsyncIterable[str]:
    from hummingbot.client.hummingbot_application import HummingbotApplication
    global global_hummingbot_pipe

    if global_hummingbot_pipe is None:
        raise RuntimeError("Not in the main process, or hummingbot wasn't started via `fork_and_start()`.")
    try:
        global_hummingbot_pipe.send((method_name, args, kwargs))
        while True:
            data = await global_hummingbot_pipe.coro_recv()
            if data is None:
                break
            yield data
    except Exception as e:  # unable to communicate with docker socket
        HummingbotApplication.main_application().notify(
            "\nError: Unable to communicate with docker socket. "
            "\nEnsure dockerd is running and /var/run/docker.sock exists, then restart Hummingbot.")
        raise e
