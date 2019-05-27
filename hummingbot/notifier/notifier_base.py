class NotifierBase:
    def __init__(self):
        pass

    def send_msg(self, msg: str):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError
