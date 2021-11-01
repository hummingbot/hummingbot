#!/usr/bin/env python

import builtins
import json
import logging
import pathlib
from collections.abc import MutableMapping as MutableMappingABC
from typing import Dict, Iterator, List, MutableMapping

import asyncssh
from prompt_toolkit import print_formatted_text
from prompt_toolkit.contrib.ssh import PromptToolkitSSHServer
from ptpython.repl import embed


class MergedNamespace(MutableMappingABC):
    def __init__(self, *mappings):
        self._mappings: List[MutableMapping] = list(mappings)
        self._local_namespace = {}

    def __setitem__(self, k, v) -> None:
        self._local_namespace[k] = v

    def __delitem__(self, v) -> None:
        for m in [self._local_namespace] + self._mappings:
            if v in m:
                del m[v]

    def __getitem__(self, k):
        for m in [self._local_namespace] + self._mappings:
            if k in m:
                return m[k]
        raise KeyError(k)

    def __len__(self) -> int:
        return sum(len(m) for m in [self._local_namespace] + self._mappings)

    def __iter__(self) -> Iterator[any]:
        for mapping in [self._local_namespace] + self._mappings:
            for k in mapping:
                yield k

    def __repr__(self) -> str:
        dict_repr: Dict[str, any] = dict(self.items())
        return f"{self.__class__.__name__}({json.dumps(dict_repr)})"


def add_diagnosis_tools(local_vars: MutableMapping):
    from .diagnosis import active_tasks
    local_vars["active_tasks"] = active_tasks


def ensure_key():
    file_name = ".debug_console_ssh_host_key"
    path = pathlib.Path(file_name)
    if not path.exists():
        rsa_key = asyncssh.generate_private_key("ssh-rsa")
        path.write_bytes(rsa_key.export_private_key())
    return str(path)


async def start_management_console(local_vars: MutableMapping,
                                   host: str = "localhost",
                                   port: int = 8212):
    add_diagnosis_tools(local_vars)

    async def interact(_=None):
        globals_dict = {
            "__name__": "__main__",
            "__doc__": None,
            "__package__": "",
            "__builtins__": builtins,
            "print": print_formatted_text,
        }
        await embed(return_asyncio_coroutine=True, locals=local_vars, globals=globals_dict)

    ssh_server = PromptToolkitSSHServer(interact=interact)
    await asyncssh.create_server(
        lambda: ssh_server, host, port, server_host_keys=[ensure_key()]
    )
    logging.getLogger(__name__).info(
        f"Started SSH debug console. Connect by running `ssh user@{host} -p {port}`. Exit with `CTRL + D`."
    )
