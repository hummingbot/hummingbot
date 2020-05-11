#!/usr/bin/env python

import asyncio
import aioconsole
from collections.abc import MutableMapping as MutableMappingABC
import json
import logging
from typing import Iterator, MutableMapping, List, Dict


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


async def start_management_console(local_vars: MutableMapping,
                                   host: str = "localhost",
                                   port: int = 8211,
                                   banner: str = "hummingbot") -> asyncio.base_events.Server:
    add_diagnosis_tools(local_vars)

    def factory_method(*args, **kwargs):
        from aioconsole.code import AsynchronousConsole
        return AsynchronousConsole(locals=local_vars, *args, **kwargs)

    retval = await aioconsole.start_interactive_server(host=host, port=port, banner=banner,
                                                       factory=factory_method)
    logging.getLogger(__name__).info(f"Started debug console at {host}:{port}.")
    return retval
