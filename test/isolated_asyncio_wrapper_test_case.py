import asyncio
import functools
import unittest
from typing import Any, Awaitable, Callable, Coroutine, Optional, TypeVar

T = TypeVar("T")


def async_to_sync(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """
    Decorator to convert an async function into a function that can be called in sync context.

    If there's an existing running loop, it uses `run_until_complete()` to execute the coroutine.
    Otherwise, it uses `asyncio.run()`.

    :param func: The async function to be converted.
    :type func: Callable[..., Any]
    :return: The wrapped synchronous function.
    :rtype: Callable[..., Any]

    Usage:

    .. code-block:: python

        from my_decorators import async_to_sync_in_loop

        class MyClass:
            @async_to_sync_in_loop
            async def async_method(self) -> str:
                await asyncio.sleep(1)
                return "Hello, World!"

        my_instance = MyClass()
        result = my_instance.async_method()
        print(result)  # Output: Hello, World!
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            loop: asyncio.AbstractEventLoop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            return asyncio.run(func(*args, **kwargs))

        result: T = loop.run_until_complete(func(*args, **kwargs))
        return result

    return wrapper


class IsolatedAsyncioWrapperTestCase(unittest.IsolatedAsyncioTestCase):
    """
    Custom test case class that wraps `unittest.IsolatedAsyncioTestCase`.

    This class provides additional functionality to set up and tear down the asyncio event loop for each test case.
    It ensures that each test case runs in an isolated asyncio event loop, preventing interference between test cases.

    Example usage:
    ```python
    class MyTestCase(IsolatedAsyncioWrapperTestCase):
        async def test_my_async_function(self):
            # Test your async function here
            ...
    ```

    Note:
    - It is important to make sure that all async functions in the test case are prefixed with the `async` keyword.
    - This class assumes that the tests are defined as methods in a subclass.

    Attributes:
    - `main_event_loop`: The reference to the main asyncio event loop.
    """
    main_event_loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            cls.main_event_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            cls.main_event_loop = None

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.main_event_loop is not None:
            asyncio.set_event_loop(cls.main_event_loop)
        cls.main_event_loop = None
        super().tearDownClass()


class LocalClassEventLoopWrapperTestCase(unittest.TestCase):
    """
    Custom test case class that wraps `unittest.TestCase`.

    This class provides additional functionality to manage the main event loop and a local event loop for tests.
    It ensures that each test case runs in a local asyncio event loop, preventing interference between test suites.

    Example usage:
    ```python
    class MyTestCase(LocalClassEventLoopWrapperTestCase):
        def test_my_async_function(self):
            self.local_event_loop.run_until_complete(asyncio.sleep(0.1))
            ...
    ```

    Note:
    - It is important to make sure that all async functions in the test case are prefixed with the `async` keyword.
    - This class assumes that the tests are defined as methods in a subclass.

    Attributes:
    - `main_event_loop`: The reference to the main asyncio event loop.
    - `local_event_loop`: The local asyncio event loop used for each test case.
    """
    main_event_loop: Optional[asyncio.AbstractEventLoop] = None
    local_event_loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            cls.main_event_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            cls.main_event_loop = None

        cls.local_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.local_event_loop)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.local_event_loop is not None and cls.local_event_loop.is_running():
            cls.local_event_loop.stop()

        if cls.local_event_loop is not None and not cls.local_event_loop.is_closed():
            cls.local_event_loop.close()
            cls.local_event_loop = None

        cls.local_event_loop = None

        asyncio.set_event_loop(cls.main_event_loop)
        cls.main_event_loop = None
        super().tearDownClass()

    def run_async_with_timeout(self, coro: Awaitable, timeout: float = 1.0) -> Any:
        """
        Run the given coroutine with a timeout.

        :param Awaitable coro: The coroutine to be executed.
        :param float timeout: The timeout value in seconds.
        :return: The result of the coroutine.
        :rtype: Any
        """
        return self.local_event_loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))


class LocalTestEventLoopWrapperTestCase(unittest.TestCase):
    """
    Custom test case class that wraps `unittest.TestCase`.

    This class provides additional functionality to manage the main event loop and a local event loop for each test.
    It ensures that each test case runs in a local asyncio event loop, preventing interference between test suites.

    Example usage:
    ```python
    class MyTestCase(LocalTestEventLoopWrapperTestCase):
        def test_my_async_function(self):
            self.local_event_loop.run_until_complete(asyncio.sleep(0.1))
            ...
    ```

    Note:
    - It is important to make sure that all async functions in the test case are prefixed with the `async` keyword.
    - This class assumes that the tests are defined as methods in a subclass.

    Attributes:
    - `main_event_loop`: The reference to the main asyncio event loop.
    - `local_event_loop`: The local asyncio event loop used for each test case.
    """
    main_event_loop: Optional[asyncio.AbstractEventLoop] = None
    local_event_loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        try:
            cls.main_event_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            cls.main_event_loop = None

    def setUp(self) -> None:
        super().setUp()
        self.local_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.local_event_loop)
        self.assertEqual(asyncio.get_event_loop(), self.local_event_loop)

    def tearDown(self) -> None:
        if self.local_event_loop is not None and self.local_event_loop.is_running():
            self.local_event_loop.stop()
        if self.local_event_loop is not None and not self.local_event_loop.is_closed():
            self.local_event_loop.close()
            self.local_event_loop = None
        super().tearDown()

    @classmethod
    def tearDownClass(cls) -> None:
        asyncio.set_event_loop(cls.main_event_loop)
        cls.main_event_loop = None
        super().tearDownClass()

    def run_async_with_timeout(self, coro: Awaitable, timeout: float = 1.0) -> Any:
        """
        Run the given coroutine with a timeout.

        :param Awaitable coro: The coroutine to be executed.
        :param float timeout: The timeout value in seconds.
        :return: The result of the coroutine.
        :rtype: Any
        """
        return self.local_event_loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
