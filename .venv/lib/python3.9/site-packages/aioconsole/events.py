"""Provide an interactive event loop class."""

import asyncio
import functools

from . import server
from . import console


class InteractiveEventLoop(asyncio.SelectorEventLoop):
    """Event loop running a python console."""

    console_class = console.AsynchronousConsole

    def __init__(
        self,
        *,
        selector=None,
        locals=None,
        banner=None,
        serve=None,
        prompt_control=None,
    ):
        self.console = None
        self.console_task = None
        self.console_server = None
        super().__init__(selector=selector)
        # Factory
        self.factory = lambda streams: self.console_class(
            streams, locals=locals, prompt_control=prompt_control, loop=self
        )
        # Local console
        if serve is None:
            self.console = self.factory(None)
            coro = self.console.interact(banner, stop=True, handle_sigint=True)
            self.console_task = asyncio.ensure_future(coro, loop=self)
        # Serving console
        else:
            host, port = serve
            coro = server.start_interactive_server(
                self.factory, host=host, port=port, banner=banner, loop=self
            )
            self.console_server = self.run_until_complete(coro)
            server.print_server(self.console_server)

    def close(self):
        if self.console_task and not self.is_running():
            asyncio.Future.cancel(self.console_task)
        super().close()

    def __del__(self):
        if self.console_task and self.console_task.done():
            self.console_task.exception()
        try:
            super().__del__()
        except AttributeError:
            pass


class InteractiveEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Policy to use the interactive event loop by default."""

    def __init__(self, *, locals=None, banner=None, serve=None, prompt_control=None):
        self._loop_factory = functools.partial(
            InteractiveEventLoop,
            locals=locals,
            banner=banner,
            serve=serve,
            prompt_control=prompt_control,
        )
        super().__init__()


def set_interactive_policy(
    *, locals=None, banner=None, serve=None, prompt_control=None
):
    """Use an interactive event loop by default."""
    policy = InteractiveEventLoopPolicy(
        locals=locals, banner=banner, serve=serve, prompt_control=prompt_control
    )
    asyncio.set_event_loop_policy(policy)


def run_console(*, locals=None, banner=None, serve=None, prompt_control=None):
    """Run the interactive event loop."""
    loop = InteractiveEventLoop(
        locals=locals, banner=banner, serve=serve, prompt_control=prompt_control
    )
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
