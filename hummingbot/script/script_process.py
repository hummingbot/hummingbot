import asyncio
import importlib
import inspect
import os
from multiprocessing import Queue
from hummingbot.script.script_base import ScriptBase


def run_script(script_file_name: str, parent_queue: Queue, child_queue: Queue, queue_check_interval: float):
    script_class = import_script_sub_class(script_file_name)
    script = script_class()
    script.assign_process_init(parent_queue, child_queue, queue_check_interval)
    ev_loop = asyncio.get_event_loop()
    ev_loop.run_until_complete(script.listen_to_parent())


def import_script_sub_class(script_file_name: str):
    name = os.path.basename(script_file_name).split(".")[0]
    spec = importlib.util.spec_from_file_location(name, script_file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for x in dir(module):
        obj = getattr(module, x)
        if inspect.isclass(obj) and issubclass(obj, ScriptBase) and obj.__name__ != "ScriptBase":
            return obj
