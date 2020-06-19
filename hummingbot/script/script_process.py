import asyncio
import importlib
from hummingbot.script.script_base import ScriptBase


def run_script(parent_queue, child_queue):
    script = ScriptBase(parent_queue, child_queue)
    ev_loop = asyncio.get_event_loop()
    ev_loop.run_until_complete(script.listen_to_parent())


def import_script_module(script_module_name, script_file_name: str):
    spec = importlib.util.spec_from_file_location(script_module_name, script_file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
