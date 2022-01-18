import docker
import types


def start_docker(queue, event):
    docker_client = docker.APIClient(base_url='unix://var/run/docker.sock')
    while True:
        try:
            try:
                method, kwargs = queue.recv()
            except Exception:
                break
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
