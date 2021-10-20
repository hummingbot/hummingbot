import logging
import json
from logging import StreamHandler

from urllib.request import Request, urlopen


class Slack:
    def __init__(self, *, url):
        self.url = url
        self.headers = {"Content-type": "application/json"}
        self.method = "POST"

    def post(self, **kwargs):
        data = json.dumps(kwargs).encode()
        req = Request(self.url, data=data, headers=self.headers, method=self.method)
        return urlopen(req).read().decode()


class SlackWebhookLog:
    def __init__(self, webhook_url: str, project_name: str):
        self.slack = Slack(url=webhook_url)
        self.project_name = project_name

    def send(self, data):
        message = f"#{self.project_name}\n\n{data}"
        self.slack.post(text=message)


class SlackWebhookHandler(StreamHandler):
    def __init__(
            self,
            webhook_url: str,
            project_name: str = "hummingbot",
            level: int = logging.ERROR,
    ):

        super(SlackWebhookHandler, self).__init__()
        self.slack_broker = SlackWebhookLog(webhook_url, project_name)
        self.setLevel(level)

    def emit(self, record):
        msg = self.format(record)
        self.slack_broker.send(msg)
