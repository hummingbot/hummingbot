import argparse


def help_(hb: "HummingbotApplication", command):
    if command == 'all':
        hb._notify(hb.parser.format_help())
    else:
        subparsers_actions = [
            action for action in hb.parser._actions if isinstance(action, argparse._SubParsersAction)]

        for subparsers_action in subparsers_actions:
            subparser = subparsers_action.choices.get(command)
            hb._notify(subparser.format_help())

