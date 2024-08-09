import asyncio


class ProgrammableV4Client():
    def __init__(self):
        self._cancel_order_responses = asyncio.Queue()
        self._place_order_responses = asyncio.Queue()

    async def cancel_order(self, *args, **kwargs):
        response = await self._cancel_order_responses.get()
        return response

    async def place_order(self, *args, **kwargs):
        response = await self._place_order_responses.get()
        return response
