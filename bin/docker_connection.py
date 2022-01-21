import docker
import types
import aioprocessing
from typing import Optional


def start_docker(queue: aioprocessing.AioConnection,
                 event: aioprocessing.AioEvent,
                 docker_client: Optional[docker.APIClient] = None):
    try:
        while True:
            try:
                method, kwargs = queue.recv()

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
    except Exception:
        pass
