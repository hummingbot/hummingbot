import asyncio
import concurrent.futures
import time
import unittest
from test.isolated_asyncio_wrapper_test_case import (
    IsolatedAsyncioWrapperTestCase,
    LocalClassEventLoopWrapperTestCase,
    LocalTestEventLoopWrapperTestCase,
)


class TestMainEventLoop(unittest.TestCase):
    def test_main_event_loop(self):
        loop = asyncio.get_event_loop()

        async def foo():
            return "success"

        result = loop.run_until_complete(foo())
        self.assertEqual(result, "success")

    def test_multiple_async_functions(self):
        loop = asyncio.get_event_loop()

        async def foo():
            return "success"

        async def bar():
            return "success"

        result = loop.run_until_complete(asyncio.gather(foo(), bar()))
        self.assertEqual(result, ["success", "success"])

    def test_exception_handling(self):
        loop = asyncio.get_event_loop()

        async def foo():
            raise ValueError("Test exception")

        with self.assertRaises(ValueError):
            loop.run_until_complete(foo())


class TestIsolated(IsolatedAsyncioWrapperTestCase):
    async def test_isolated(self):
        await asyncio.sleep(0.1)

    async def test_another(self):
        await asyncio.sleep(0.1)


class TestRunClassEventLoop(LocalClassEventLoopWrapperTestCase):
    def test_run(self):
        asyncio.run(asyncio.sleep(0.1))

    def test_another(self):
        asyncio.run(asyncio.sleep(0.1))


class TestRunTestEventLoop(LocalTestEventLoopWrapperTestCase):
    def test_run(self):
        asyncio.run(asyncio.sleep(0.1))

    def test_another(self):
        asyncio.run(asyncio.sleep(0.1))


class TestParallelExecution(unittest.TestCase):
    def test_parallel_execution(self):
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = [executor.submit(self.run_test, test) for test in
                       [TestMainEventLoop, TestRunClassEventLoop, TestIsolated, TestRunTestEventLoop,
                        TestMainEventLoop]]
            for future in concurrent.futures.as_completed(futures):
                future.result()  # Raises an exception if the test failed

    @staticmethod
    def run_test(test_case):
        suite = unittest.TestSuite()
        for test in unittest.defaultTestLoader.getTestCaseNames(test_case):
            suite.addTest(test_case(test))
        unittest.TextTestRunner().run(suite)


class TestIsolatedAsyncioWrapperTestCase(unittest.TestCase):
    def test_setUpClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        IsolatedAsyncioWrapperTestCase.setUpClass()
        self.assertIsNotNone(IsolatedAsyncioWrapperTestCase.main_event_loop)
        self.assertEqual(self.main_loop, IsolatedAsyncioWrapperTestCase.main_event_loop)

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_setUpClass_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        # Call setUpClass and verify that it does not create a new event loop
        IsolatedAsyncioWrapperTestCase.setUpClass()
        self.assertIsNone(IsolatedAsyncioWrapperTestCase.main_event_loop)

        # Verify that get_event_loop still raises a RuntimeError, indicating that no event loop exists
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_tearDownClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        IsolatedAsyncioWrapperTestCase.main_event_loop = self.main_loop
        IsolatedAsyncioWrapperTestCase.tearDownClass()
        self.assertIsNone(IsolatedAsyncioWrapperTestCase.main_event_loop)
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_tearDownClass_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        IsolatedAsyncioWrapperTestCase.tearDownClass()
        self.assertIsNone(IsolatedAsyncioWrapperTestCase.main_event_loop)

        # Verify that get_event_loop still raises a RuntimeError, indicating that no event loop exists
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_exception_in_test_case(self):
        IsolatedAsyncioWrapperTestCase.setUpClass()

        try:
            # Simulate a test case that raises an exception
            raise Exception("Test exception")
        except Exception:
            pass

        # Despite the exception, tearDownClass should still correctly clean up the event loop
        IsolatedAsyncioWrapperTestCase.tearDownClass()
        self.assertIsNone(IsolatedAsyncioWrapperTestCase.main_event_loop)


class TestLocalClassEventLoopWrapperTestCase(unittest.TestCase):
    def setUp(self):
        self.test_case = LocalClassEventLoopWrapperTestCase()
        self.test_case.setUpClass()

    def tearDown(self):
        self.test_case.tearDownClass()

    def test_setUpClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        LocalClassEventLoopWrapperTestCase.setUpClass()
        self.assertIsNotNone(LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertEqual(self.main_loop, LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertNotEqual(self.main_loop, LocalClassEventLoopWrapperTestCase.local_event_loop)

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_setUpClass_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        # Call setUpClass and verify that it does not create a new event loop
        LocalClassEventLoopWrapperTestCase.setUpClass()
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertEqual(asyncio.get_event_loop(), LocalClassEventLoopWrapperTestCase.local_event_loop)

    def test_tearDownClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        LocalClassEventLoopWrapperTestCase.main_event_loop = self.main_loop
        LocalClassEventLoopWrapperTestCase.tearDownClass()
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.local_event_loop)
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_tearDownClass_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        LocalClassEventLoopWrapperTestCase.tearDownClass()
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.local_event_loop)

        # Verify that get_event_loop still raises a RuntimeError, indicating that no event loop exists
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_exception_in_test_case(self):
        IsolatedAsyncioWrapperTestCase.setUpClass()

        try:
            # Simulate a test case that raises an exception
            raise Exception("Test exception")
        except Exception:
            pass

        # Despite the exception, tearDownClass should still correctly clean up the event loop
        LocalClassEventLoopWrapperTestCase.tearDownClass()
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.main_event_loop)

    def test_run_async_with_timeout(self):
        self.test_case.setUp()

        # Test a coroutine that finishes before the timeout
        start_time = time.time()
        result = self.test_case.run_async_with_timeout(asyncio.sleep(0.1), timeout=1.0)
        end_time = time.time()
        self.assertIsNone(result)
        self.assertLess(end_time - start_time, 1.0)

        # Test a coroutine that doesn't finish before the timeout
        with self.assertRaises(asyncio.TimeoutError):
            self.test_case.run_async_with_timeout(asyncio.sleep(2.0), timeout=1.0)

        self.test_case.tearDown()


class TestLocalTestEventLoopWrapperTestCase(unittest.TestCase):
    def setUp(self):
        self.test_case = LocalTestEventLoopWrapperTestCase()
        self.test_case.setUpClass()

    def tearDown(self):
        self.test_case.tearDownClass()

    def test_setUp_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        self.test_case.setUp()
        self.assertIsNotNone(self.test_case.local_event_loop)
        self.assertEqual(self.test_case.local_event_loop, asyncio.get_event_loop())
        self.assertNotEqual(self.main_loop, self.test_case.local_event_loop)

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_setUp_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        self.test_case.setUp()
        self.assertIsNotNone(self.test_case.local_event_loop)
        self.assertEqual(self.test_case.local_event_loop, asyncio.get_event_loop())

    def test_tearDown_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        self.test_case.local_event_loop = self.main_loop
        self.test_case.tearDown()
        self.assertIsNone(self.test_case.local_event_loop)
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_tearDown_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        self.test_case.tearDown()
        self.assertIsNone(self.test_case.local_event_loop)

        # Verify that get_event_loop still raises a RuntimeError, indicating that no event loop exists
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_tearDownClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        LocalTestEventLoopWrapperTestCase.main_event_loop = self.main_loop
        self.test_case.tearDownClass()
        self.assertIsNone(LocalTestEventLoopWrapperTestCase.main_event_loop)
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_tearDownClass_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        self.test_case.tearDownClass()
        self.assertIsNone(self.test_case.main_event_loop)

        # Verify that get_event_loop still raises a RuntimeError, indicating that no event loop exists
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_run_async_with_timeout(self):
        self.test_case.setUp()

        # Test a coroutine that finishes before the timeout
        start_time = time.time()
        result = self.test_case.run_async_with_timeout(asyncio.sleep(0.1), timeout=1.0)
        end_time = time.time()
        self.assertIsNone(result)
        self.assertLess(end_time - start_time, 1.0)

        # Test a coroutine that doesn't finish before the timeout
        with self.assertRaises(asyncio.TimeoutError):
            self.test_case.run_async_with_timeout(asyncio.sleep(2.0), timeout=1.0)

        self.test_case.tearDown()


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTest(TestMainEventLoop('test_main_event_loop'))
    suite.addTest(TestMainEventLoop('test_multiple_async_functions'))
    suite.addTest(TestMainEventLoop('test_exception_handling'))

    suite.addTest(TestParallelExecution('test_parallel_execution'))

    suite.addTest(TestIsolated('test_isolated'))
    suite.addTest(TestIsolated('test_another'))

    suite.addTest(TestRunClassEventLoop('test_run'))
    suite.addTest(TestRunClassEventLoop('test_another'))

    suite.addTest(TestRunTestEventLoop('test_run'))
    suite.addTest(TestRunTestEventLoop('test_another'))

    suite.addTest(TestMainEventLoop('test_main_event_loop'))
    suite.addTest(TestMainEventLoop('test_multiple_async_functions'))
    suite.addTest(TestMainEventLoop('test_exception_handling'))

    # Coverage tests
    suite.addTest(TestIsolatedAsyncioWrapperTestCase('test_setUpClass'))
    suite.addTest(TestIsolatedAsyncioWrapperTestCase('test_tearDownClass'))
    suite.addTest(TestLocalClassEventLoopWrapperTestCase('test_setUpClass'))
    suite.addTest(TestLocalClassEventLoopWrapperTestCase('test_tearDownClass'))
    suite.addTest(TestLocalTestEventLoopWrapperTestCase('test_setUp'))
    suite.addTest(TestLocalTestEventLoopWrapperTestCase('test_tearDown'))
    suite.addTest(TestLocalTestEventLoopWrapperTestCase('test_tearDownClass'))

    return suite


if __name__ == "__main__":
    unittest.main()
