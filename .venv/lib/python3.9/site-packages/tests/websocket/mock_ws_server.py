import asyncio
from collections import namedtuple

import websockets


class MockWebSocketServer:
    def __init__(self, host="localhost", port=8765):
        self.start_server = None
        self.host = host
        self.port = port
        self.server = None
        self.active_websockets = set()

    async def handler(self, websocket):
        self.active_websockets.add(websocket)
        try:
            async for message in websocket:
                # Echo the message back to the client
                await websocket.send(message)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.active_websockets.discard(websocket)

    def initialize_server(self):
        return websockets.serve(self.handler, self.host, self.port)

    async def start(self):
        self.start_server = self.initialize_server()
        self.server = await self.start_server

    async def stop(self):
        WebSocketTask = namedtuple("WebSocketTask", ["ws", "task"])

        tasks = [
            WebSocketTask(ws, asyncio.create_task(ws.close()))
            for ws in self.active_websockets
        ]
        await asyncio.gather(*(task.task for task in tasks))
        self.active_websockets -= {task.ws for task in tasks}

        if self.server:
            self.server.close()
            await self.server.wait_closed()  # Ensure the server is fully closed

    async def restart_with_error(self):
        await self.trigger_connection_closed_error()
        await self.stop()
        await asyncio.sleep(1)  # Short delay to ensure the port is freed up
        await self.start()

    async def trigger_connection_closed_error(self):
        WebSocketTask = namedtuple("WebSocketTask", ["ws", "task"])

        tasks = [
            WebSocketTask(
                ws, asyncio.create_task(ws.close(code=4000, reason="Abnormal closure"))
            )
            for ws in self.active_websockets
        ]
        await asyncio.gather(*(task.task for task in tasks))
        self.active_websockets -= {task.ws for task in tasks}


# Function to start the mock server
async def start_mock_server():
    server = MockWebSocketServer()
    await server.start()
    return server
