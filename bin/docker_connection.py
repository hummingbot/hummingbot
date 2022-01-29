import aioprocessing
import asyncio
import docker
from multiprocessing import Process
import types
from typing import Callable, Dict, Any, Union, List


async def _start_docker_async(
        docker_pipe: aioprocessing.AioConnection,
        evt: aioprocessing.AioEvent
):
    docker_client: docker.APIClient = docker.APIClient(base_url="unix://var/run/docker.sock")
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    while True:
        try:
            method_name: str
            method_args: Union[Dict[str, Any], List[Any]]
            method_name, method_args = await docker_pipe.coro_recv()
        except Exception:
            # Any input that isn't a tuple will cause the controller process to exit.
            return

        try:
            method: Callable = getattr(docker_client, method_name)
            if isinstance(method_args, list):
                response = await ev_loop.run_in_executor(
                    None,
                    lambda: method(method_args[0], **method_args[1])
                )
            else:
                response = await ev_loop.run_in_executor(
                    None,
                    lambda: method(**method_args)
                )

            if isinstance(response, types.GeneratorType):
                evt.set()
                for stream in response:
                    await docker_pipe.coro_send(stream)
                await docker_pipe.coro_send(None)
                evt.clear()
            else:
                await docker_pipe.coro_send(response)
        except Exception as e:
            await docker_pipe.coro_send(e)


def _start_docker(
        docker_pipe: aioprocessing.AioConnection,
        evt: aioprocessing.AioEvent
):
    ev_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    asyncio.set_event_loop(ev_loop)
    ev_loop.run_until_complete(_start_docker_async(docker_pipe, evt))


def fork_and_start(main_function: Callable):
    p1, p2 = aioprocessing.AioPipe()
    evt: aioprocessing.AioEvent = aioprocessing.AioEvent()
    docker_process: Process = Process(target=_start_docker, args=(p2, evt))

    try:
        # fork the docker process as child.
        docker_process.start()

        # run the main function as parent.
        main_function(p1, evt)
    finally:
        # send a non-tuple to the Docker controller process to cause it to exit.
        p1.send(None)

        # close pipes.
        p1.close()
        p2.close()

        # wait for Docker controller process clean up.
        docker_process.join()
