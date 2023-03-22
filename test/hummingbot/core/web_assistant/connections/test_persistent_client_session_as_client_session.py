import asyncio
import threading
import unittest
import weakref

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.persistent_client_session import PersistentClientSession


class TestPersistentClientSessionAsClientSession(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.persistent_session = PersistentClientSession()
        self.client_session: weakref.ProxyTypes = self.persistent_session()

    async def asyncTearDown(self):
        try:
            await self.client_session.close()
        except Exception:
            pass
        await self.persistent_session.close()
        await asyncio.sleep(0)

    async def test_get(self):
        async with self.persistent_session.get('https://httpbin.org/get') as response:
            self.assertEqual(response.status, 200)
            self.assertIn('application/json', response.headers['Content-Type'])
            data = await response.json()
            self.assertIn('httpbin', data['url'])

    async def test_post(self):
        payload = {'key': 'value'}
        url = 'https://httpbin.org/post'

        # Mock the POST request using aioresponses
        expected_response = {'json': payload}
        with aioresponses() as m:
            m.post(url, payload=expected_response, repeat=True)

            # Make the request using ClientSession and PersistentClientSession
            async with self.persistent_session.post('https://httpbin.org/post', data=payload) as response:
                self.assertEqual(response.status, 200)
                self.assertIn('application/json', response.headers['Content-Type'])
                data = await response.json()
                self.assertEqual(data['json'], payload)

            async with aiohttp.ClientSession() as session:
                async with session.post('https://httpbin.org/post', data=payload) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn('application/json', response.headers['Content-Type'])
                    data = await response.json()
                    self.assertEqual(data['json'], payload)

    async def test_put(self):
        payload = {'key': 'value'}
        async with self.persistent_session.put('https://httpbin.org/put', json=payload) as response:
            self.assertEqual(response.status, 200)
            self.assertIn('application/json', response.headers['Content-Type'])
            data = await response.json()
            self.assertEqual(payload, data['json'])

    async def test_patch(self):
        payload = {'key': 'value'}
        async with self.persistent_session.patch('https://httpbin.org/patch', json=payload) as response:
            self.assertEqual(response.status, 200)
            self.assertIn('application/json', response.headers['Content-Type'])
            data = await response.json()
            self.assertEqual(payload, data['json'])

    async def test_delete(self):
        async with self.persistent_session.delete('https://httpbin.org/delete') as response:
            self.assertEqual(response.status, 200)

    async def test_head(self):
        async with self.persistent_session.head('https://httpbin.org/get') as response:
            self.assertEqual(response.status, 200)

    async def test_options(self):
        async with self.persistent_session.options('https://httpbin.org/get') as response:
            self.assertEqual(response.status, 200)
            self.assertIn('GET', response.headers['Allow'])

    async def test_cookie_jar(self):
        self.assertIsNotNone(self.persistent_session.cookie_jar)

    async def test_close_method_is_monitored(self):
        async with self.persistent_session as session:
            thread_id = threading.get_ident()
            self.assertTrue(self.persistent_session.has_live_session(thread_id=thread_id))
            await session.close()
            self.assertFalse(self.persistent_session.has_live_session(thread_id=thread_id))

            with self.assertRaises(RuntimeError) as e:
                await session.get('http://www.example.com')

            # Trying to call 'get' with a closed session. The session is independent of the monitored session
            self.assertEqual(str(e.exception), 'Session is closed')

            with self.assertRaises(AttributeError) as e:
                await self.persistent_session.get('http://www.example.com')

            # Trying to call 'get' with a closed session the set the _session = None (None.get())
            self.assertEqual(str(e.exception), "'PersistentClientSession', nor 'NoneType' object has attribute 'get'")

    async def test_monitor_close_method_with_aioresponses(self):
        with aioresponses() as m:
            m.get('http://www.example.com', payload={})
            m.get('http://www.example.com', payload={})

            async with self.persistent_session as session:
                thread_id = threading.get_ident()
                self.assertFalse(not self.persistent_session.has_live_session(thread_id=thread_id))

                await self.persistent_session.get('http://www.example.com')
                await self.persistent_session.get('http://www.example.com')

                self.assertFalse(not self.persistent_session.has_live_session(thread_id=thread_id))

                await self.persistent_session.close()

                self.assertTrue(not self.persistent_session.has_live_session(thread_id=thread_id))

                with self.assertRaises(AttributeError) as e:
                    await self.persistent_session.get('http://www.example.com')

                # Trying to call 'get' with a closed session the set the _session = None (None.get())
                self.assertEqual(str(e.exception),
                                 "'PersistentClientSession', nor 'NoneType' object has attribute 'get'")

                with self.assertRaises(RuntimeError) as e:
                    await session.get('http://www.example.com')

                # Trying to call 'get' with a closed session. The session is independent of the monitored session
                self.assertEqual(str(e.exception), 'Session is closed')
