from flask import Flask, jsonify
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
api = Flask(__name__)

verification_token = global_config_map.get("slack_verification_token").value


@api.route('/test', methods=['GET'])
def test():
    return 'Here'


@api.route('/slack/start', methods=['POST'])
def start():
    hb = HummingbotApplication.main_application()
    hb._handle_command('start')
    return jsonify('Started')


@api.route('/slack/stop', methods=['POST'])
def stop():
    hb = HummingbotApplication.main_application()
    hb._handle_command('stop')
    return jsonify('Stopped')


@api.route('/slack/status', methods=['POST'])
def status():
    hb = HummingbotApplication.main_application()
    hb._handle_command('status')
    return jsonify('status')


@api.route('/slack/history', methods=['POST'])
def history():
    hb = HummingbotApplication.main_application()
    hb._handle_command('history')
    return jsonify('history')


@api.route('/slack/balance', methods=['POST'])
def balance():
    hb = HummingbotApplication.main_application()
    hb._handle_command('balance')
    return jsonify('Balance`')


def run_api():
    api.run(port=5000)
