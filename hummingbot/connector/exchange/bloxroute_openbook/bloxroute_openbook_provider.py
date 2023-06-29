import asyncio

import bxsolana


class BloxrouteOpenbookProvider(bxsolana.provider.WsProvider):
    _provider_connect_task: asyncio.Task

    def __init__(self, endpoint: str, auth_header: str, private_key: str):
        super().__init__(endpoint=endpoint, auth_header=auth_header, private_key=private_key)
        self._connect()

    def _connect(self):
        self._provider_connect_task = asyncio.create_task(super().connect())

    async def wait_connect(self):
        if self._provider_connect_task:
            await self._provider_connect_task
        else:
            raise Exception("provider_connect_task not initialized")

    @property
    def connected(self) -> bool:
        if self._provider_connect_task:
            return self._provider_connect_task.done()
        else:
            raise Exception("provider_connect_task not initialized")
