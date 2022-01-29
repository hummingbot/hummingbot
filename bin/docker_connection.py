import docker
import types
import aioprocessing


def start_docker(queue: aioprocessing.AioConnection,
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
