import asyncio
import sys
import threading
import unittest
from unittest.mock import AsyncMock, patch

from _weakref import ReferenceType
from aiohttp import ClientSession

from hummingbot.core.web_assistant.connections.persistent_client_session import (
    NotWithinAsyncFrameworkError,
    PersistentClientSession,
)


class AsyncContextManagerMock(AsyncMock):
    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, *args):
        pass


class TestPersistentClientSession(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client_type = PersistentClientSession
        if self.client_type.is_instantiated():
            self.client_type.__class__._WeakSingletonMetaclass__clear(self.client_type)

    async def asyncTearDown(self):
        print("asyncTearDown")
        await asyncio.sleep(0)

    def tearDown(self):
        print("TearDown")

    @classmethod
    def tearDownClass(cls):
        print("TearDownClass")

    def assertWasInstantiatedInThread(self, instance: PersistentClientSession, thread_id: int):
        self.assertTrue(instance.__class__.is_instantiated())
        self.assertIsInstance(instance, PersistentClientSession)
        self.assertTrue(thread_id in instance._client_sessions)
        self.assertTrue(thread_id in instance._kwargs_client_sessions)
        self.assertTrue(thread_id in instance._original_sessions_close)
        self.assertTrue(thread_id in instance._sessions_mutex)
        self.assertTrue(thread_id in instance._ref_count)
        self.assertTrue(issubclass(asyncio.Lock, type(instance._sessions_mutex.get(thread_id)), ))
        self.assertIsNotNone(instance._sessions_mutex.get(thread_id), )

    def assertInstantiatedStateInThread(self, instance: PersistentClientSession, thread_id: int):
        self.assertWasInstantiatedInThread(instance, thread_id)
        self.assertTrue(instance.__class__.is_instantiated())
        self.assertFalse(instance.has_session(thread_id=thread_id))
        self.assertFalse(instance.has_live_session(thread_id=thread_id))

    def assertWasInitializedInThread(self, instance: PersistentClientSession, thread_id: int, kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.assertWasInstantiatedInThread(instance, thread_id)
        self.assertEqual(kwargs, instance._kwargs_client_sessions.get(thread_id))

    def assertInitializedStateInThread(self, instance: PersistentClientSession, thread_id: int, kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.assertWasInitializedInThread(instance, thread_id, kwargs)
        self.assertEqual(0, instance._ref_count.get(thread_id))
        self.assertEqual(None, instance._client_sessions.get(thread_id))
        self.assertEqual(None, instance._original_sessions_close.get(thread_id))
        self.assertFalse(instance._sessions_mutex.get(thread_id).locked())
        self.assertFalse(instance.has_session(thread_id=thread_id))
        self.assertFalse(instance.has_live_session(thread_id=thread_id))

    def assertSessionOpenedStateInThread(self, instance: PersistentClientSession, thread_id: int, kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.assertWasInitializedInThread(instance, thread_id)
        self.assertEqual(kwargs, instance._kwargs_client_sessions.get(thread_id), )
        self.assertNotEqual(None, instance._client_sessions.get(thread_id))
        self.assertNotEqual(None, instance._original_sessions_close.get(thread_id))
        self.assertIsInstance(instance._client_sessions.get(thread_id), ClientSession)
        self.assertTrue(type(instance._original_sessions_close.get(thread_id)), type(ClientSession.close))
        self.assertFalse(instance._client_sessions.get(thread_id).closed)
        self.assertTrue(instance.has_session(thread_id=thread_id))
        self.assertTrue(instance.has_live_session(thread_id=thread_id))
        self.assertIsInstance(instance(), ClientSession)

    def assertSessionClosedStateInThread(self, instance: PersistentClientSession, thread_id: int):
        self.assertWasInitializedInThread(instance, thread_id)
        self.assertEqual({}, instance._kwargs_client_sessions.get(thread_id))
        self.assertEqual(None, instance._original_sessions_close.get(thread_id))
        self.assertEqual(None, instance._client_sessions.get(thread_id))
        self.assertFalse(instance.has_session(thread_id=thread_id))
        self.assertFalse(instance.has_live_session(thread_id=thread_id))
        self.assertTrue(instance.__class__.is_instantiated())

    def test_instantiated_state(self):
        thread_id: int = threading.get_ident()
        kwargs: dict = {"key": "val"}
        instance: PersistentClientSession = PersistentClientSession(key="val")

        self.assertInstantiatedStateInThread(instance, thread_id)
        self.assertInitializedStateInThread(instance, thread_id, kwargs)
        self.assertEqual(kwargs, instance._kwargs_client_sessions.get(thread_id), )

    async def test_session_opened_state(self):
        thread_id: int = threading.get_ident()
        instance: PersistentClientSession = PersistentClientSession()

        # self.assertInstantiatedStateInThread(instance, thread_id)
        session: ReferenceType[ClientSession] = instance()
        print(session)
        print(type(session))
        self.assertTrue(session is instance())
        self.assertSessionOpenedStateInThread(instance, thread_id, None)
        # instance._shared_client_sessions[thread_id] = None
        # del instance
        # gc.collect()

    async def test_session_closed_state(self):
        thread_id: int = threading.get_ident()
        instance: PersistentClientSession = PersistentClientSession()

        self.assertInstantiatedStateInThread(instance, thread_id)
        session: ClientSession = instance()
        await session.close()
        self.assertSessionClosedStateInThread(instance, thread_id)

    def test___call___raises_without_event_loop(self):
        thread_id: int = threading.get_ident()
        instance: PersistentClientSession = PersistentClientSession(key="val")
        self.assertTrue(instance.__class__.is_instantiated())
        self.assertIsInstance(instance, PersistentClientSession)
        self.assertTrue(instance is PersistentClientSession())

        # Instantiating the ClientSession using __call__ should raise the exception from ClientSession
        with self.assertRaises(Exception) as loop_error:
            asyncio.get_running_loop()
        self.assertTrue('no running event loop' in str(loop_error.exception))

        with self.assertRaises(NotWithinAsyncFrameworkError) as instance_error:
            instance()

        self.assertIsInstance(instance_error.exception, NotWithinAsyncFrameworkError)
        self.assertTrue('The event loop is not running' in str(instance_error.exception))
        self.assertTrue(issubclass(asyncio.Lock, type(instance._sessions_mutex.get(thread_id)), ))
        self.assertIsNotNone(instance._sessions_mutex.get(thread_id), )
        self.assertEqual(None, instance._client_sessions.get(thread_id), )

    async def test___call___deletes_without_reference(self):
        PersistentClientSession()
        # Without hard-reference, the instance is created and deleted immediately
        self.assertFalse(PersistentClientSession.is_instantiated())
        await asyncio.sleep(0)

    async def test___call___does_create_with_implicit_reference(self):
        client_session: ClientSession = PersistentClientSession()()
        # No explicit hard-reference, however, there is a hard reference on the stack from the Class call
        self.assertTrue(PersistentClientSession.is_instantiated())
        # The session has been created and is live
        self.assertIsInstance(client_session, ClientSession)
        self.assertFalse(client_session.closed)
        await asyncio.sleep(0)

    async def test___call___implicit_reference_cleaned_by_session_close(self):
        self.assertFalse(PersistentClientSession.is_instantiated())
        # Standalone this test you not have an entry in the _instances dict
        # However, tests ran in parallel may have created an instance
        self.assertTrue(PersistentClientSession not in PersistentClientSession._instances or PersistentClientSession._instances[PersistentClientSession] is None)
        client_session: ClientSession = PersistentClientSession()()
        # No explicit hard-reference, however, there is a hard reference on the stack from the Class call
        self.assertTrue(PersistentClientSession.is_instantiated())

        # The session has been created and is live
        self.assertTrue(2, sys.getrefcount(PersistentClientSession._instances[PersistentClientSession]))

        # The session has been created and is live
        self.assertIsInstance(client_session, ClientSession)
        self.assertFalse(client_session.closed)

        self.assertFalse(client_session.closed)
        await client_session.close()
        # The weakref proxy no longer exists since the last reference is flushed
        with self.assertRaises(ReferenceError):
            self.assertTrue(client_session.closed)

        # The instance no longer exists on the stack, the client close() cleaned-up the PersistentClientSession
        # instance
        self.assertFalse(PersistentClientSession.is_instantiated())
        instance: PersistentClientSession = PersistentClientSession()
        self.assertTrue(3, sys.getrefcount(PersistentClientSession._instances[PersistentClientSession]))
        self.assertTrue(PersistentClientSession.is_instantiated())

        # Deleting the new instance should not delete the class instance
        del instance
        self.assertTrue(2, sys.getrefcount(PersistentClientSession._instances[PersistentClientSession]))
        self.assertFalse(PersistentClientSession.is_instantiated())

        # Deleting the reference in the stack (how to do this?) should delete the class instance
        # TODO: Find a way to test that the instance is deleted when the reference in the stack is deleted
        await asyncio.sleep(0)

    async def test___call___creates_with_reference(self):
        thread_id: int = threading.get_ident()
        instance: PersistentClientSession = PersistentClientSession()

        client_session: ClientSession = instance()

        self.assertIsInstance(client_session, ClientSession)
        self.assertFalse(client_session.closed)
        self.assertTrue(thread_id in instance._client_sessions)
        self.assertEqual(client_session, instance._client_sessions[thread_id])
        # Note that this test does not generate an `ClientSession unclosed' post-run error
        # This indicates that the session is being closed properly when 'instance' gets unreferenced
        # TODO: Find a way to test that the session is closed when the instance is unreferenced
        await asyncio.sleep(0)

    @patch("hummingbot.core.web_assistant.connections.persistent_client_session.ClientSession")
    async def test___call___propagates_clientsession_exception(self, mock_client_session):
        mock_client_session.closed.return_value = False
        mock_client_session.side_effect = Exception("error creating session")

        instance: PersistentClientSession = PersistentClientSession()
        self.assertIsInstance(instance, PersistentClientSession)
        self.assertTrue(instance is PersistentClientSession())

        # Instantiating the ClientSession using __call__ should raise the exception from ClientSession
        with self.assertRaises(Exception):
            instance()

    async def test__aenter__create_async_with_instance_no_as_ref(self):
        thread_id: int = threading.get_ident()
        instance = PersistentClientSession()
        self.assertFalse(instance.has_live_session(thread_id=thread_id))
        async with instance:
            self.assertTrue(instance is PersistentClientSession())
            self.assertTrue(instance.has_live_session(thread_id=thread_id))
        # In this case, without a reference (no 'as' xxx) to the ClientSession, the session is closed
        self.assertSessionClosedStateInThread(instance, thread_id)

        await asyncio.sleep(0)

    async def test__aenter__create_async_with_instance_as(self):
        thread_id: int = threading.get_ident()
        instance = PersistentClientSession()
        async with instance as a:
            self.assertTrue(instance is PersistentClientSession())
            self.assertIsInstance(a, ClientSession)
        self.assertTrue(instance.has_live_session(thread_id=thread_id))
        self.assertTrue(instance.__class__.is_instantiated())
        await asyncio.sleep(0)

    def test_singleton_is_always_same_object(self):
        assert PersistentClientSession() is PersistentClientSession()

        class NonSingleton:
            pass

        assert NonSingleton() is not NonSingleton()

    def test_create_instance_raises_outside_event_loop(self):
        with self.assertRaises(NotWithinAsyncFrameworkError):
            PersistentClientSession()()

    # async def test_aenter(self):
    #    async with PersistentClientSession() as client:
    #        self.assertEqual(False, client.closed)
    #        await asyncio.sleep(0.1)
    #    self.assertEqual(True, client.closed)
    #    await asyncio.sleep(0.1)

    async def test_aenter_with_instance(self):
        instance = PersistentClientSession()
        async with instance as client:
            self.assertEqual(False, client.closed)
            await asyncio.sleep(0.1)
        self.assertEqual(False, client.closed)
        await asyncio.sleep(0.1)

    # async def test_aenter_with_instance_and_class(self):
    #    instance = PersistentClientSession()
    #    async with PersistentClientSession() as client:
    #        self.assertEqual(False, client.closed)
    #        await asyncio.sleep(0.1)
    #    self.assertEqual(False, client.closed)
    #    del instance
    #    self.assertEqual(True, client.closed)
    #    await asyncio.sleep(0.1)

    # async def test_aenter_with_return(self):
    #    async def return_client():
    #        async with PersistentClientSession() as client:
    #            self.assertEqual(False, client.closed)
    #            await asyncio.sleep(0.1)
    #            return client
    #
    #    client = await return_client()
    #    print("***", client)
    #    # Session is not closed, deferred to user close
    #    self.assertEqual(False, client.closed)
    #    await client.close()
    #    self.assertEqual(True, client.closed)
    #
    #    client = await return_client()
    #    print("***", client)
    #    # Session is not closed, deferred to user close
    #    self.assertEqual(False, client.closed)
    #    del client
    #    print(PersistentClientSession().has_live_session(thread_id=threading.get_ident()))
    #    await asyncio.sleep(0.1)

    async def test_aexit_not_called_on_outcontext(self):
        with patch("aiohttp.ClientSession") as mock_client_session:
            instance = PersistentClientSession()
            mock_client_session.return_value = AsyncContextManagerMock()
            async with instance:
                await asyncio.sleep(0.1)

            self.assertFalse(mock_client_session.return_value.__aexit__.called)
            self.assertEqual(mock_client_session.return_value.__aexit__.await_count, 0)
