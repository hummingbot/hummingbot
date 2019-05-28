class NotifierBase:
    def __init__(self):
        self._started = False

    def send_msg(self, msg: str):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError
