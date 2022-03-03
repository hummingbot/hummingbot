import aioprocessing
import asyncio
import docker
import logging
from multiprocessing import Process
import types
from typing import Callable, Dict, Any, List, Generator, Union

from hummingbot.core.gateway import (
    docker_ipc,
    get_gateway_container_name,
    set_hummingbot_pipe,
)

logger: logging.Logger = logging.getLogger(__name__)


async def _start_docker_controller(docker_pipe: aioprocessing.AioConnection):
    """
    Run the docker controller loop.

    Note that all the I/O operations must be converted to asynchronous operations. This allows any operations within
    this loop to be cancellable when the user desires to exit. Having any blocking I/O operation in this loop would mean
    the potential for the child process to be stuck while the user is trying to exit from Hummingbot.
    """
    initialization_error = None
    try:
        docker_client: docker.APIClient = docker.APIClient(base_url="unix://var/run/docker.sock")
    except Exception as e:
        initialization_error = e

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

        if initialization_error is not None:
            await docker_pipe.coro_send(initialization_error)
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

        # Set the pipe for docker_ipc() functions.
        set_hummingbot_pipe(p1)

        # run the main function as parent.
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
