import aioprocessing
import docker
from multiprocessing import Process
import types
from typing import Callable


def _start_docker(queue: aioprocessing.AioConnection,
                  event: aioprocessing.AioEvent):
    docker_client: docker.APIClient = docker.APIClient(base_url="unix://var/run/docker.sock")
    while True:
        try:
            method, kwargs = queue.recv()
        except Exception:
            break

        try:
            if isinstance(kwargs, list):
                response = getattr(docker_client, method)(kwargs[0], **kwargs[1])
            else:
                response = getattr(docker_client, method)(**kwargs)

            if isinstance(response, types.GeneratorType):
                event.set()
                for stream in response:
                    queue.send(stream)
                queue.send(None)
                event.clear()
            else:
                queue.send(response)
        except Exception as e:
            queue.send(e)


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
        p1.close()
        p2.close()

        if docker_process.is_alive():
            docker_process.terminate()
        docker_process.join()
