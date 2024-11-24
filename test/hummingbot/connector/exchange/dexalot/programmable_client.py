import asyncio


class ProgrammableClient():
    def __init__(self):
        self._cancel_order_responses = asyncio.Queue()
        self._place_order_responses = asyncio.Queue()
        self._get_balances_responses = asyncio.Queue()

    async def get_balances(self, *args, **kwargs):
        response = await self._get_balances_responses.get()
        return response

    async def cancel_and_add_order_list(self, *args, **kwargs):
        await self._place_order_responses.get()
        await self._cancel_order_responses.get()
        return None

    async def cancel_order_list(self, *args, **kwargs):
        response = await self._cancel_order_responses.get()
        return response
