from flask import Flask, request
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
api = Flask(__name__)

verification_token = global_config_map.get("slack_verification_token").value


@api.route('/test', methods=['GET'])
def test():
    return 'Here'


@api.route('/slack', methods=['POST'])
def start():
    hb = HummingbotApplication.main_application()
    hb._handle_command(request.json['command'])


def run_api():
    api.run(port=5002)
