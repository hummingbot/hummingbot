from wings.pubsub import PubSub


class BaseWatcher(PubSub):
    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError
