"""
Wrapper around the eventloop that gives some time to the Tkinter GUI to process
events when it's loaded and while we are waiting for input at the REPL. This
way we don't block the UI of for instance ``turtle`` and other Tk libraries.

(Normally Tkinter registers it's callbacks in ``PyOS_InputHook`` to integrate
in readline. ``prompt-toolkit`` doesn't understand that input hook, but this
will fix it for Tk.)
"""

from __future__ import annotations

import sys
import time

from prompt_toolkit.eventloop import InputHookContext

__all__ = ["inputhook"]


def _inputhook_tk(inputhook_context: InputHookContext) -> None:
    """
    Inputhook for Tk.
    Run the Tk eventloop until prompt-toolkit needs to process the next input.
    """
    # Get the current TK application.
    import _tkinter  # Keep this imports inline!
    import tkinter

    root = tkinter._default_root  # type: ignore

    def wait_using_filehandler() -> None:
        """
        Run the TK eventloop until the file handler that we got from the
        inputhook becomes readable.
        """
        # Add a handler that sets the stop flag when `prompt-toolkit` has input
        # to process.
        stop = [False]

        def done(*a: object) -> None:
            stop[0] = True

        root.createfilehandler(inputhook_context.fileno(), _tkinter.READABLE, done)

        # Run the TK event loop as long as we don't receive input.
        while root.dooneevent(_tkinter.ALL_EVENTS):
            if stop[0]:
                break

        root.deletefilehandler(inputhook_context.fileno())

    def wait_using_polling() -> None:
        """
        Windows TK doesn't support 'createfilehandler'.
        So, run the TK eventloop and poll until input is ready.
        """
        while not inputhook_context.input_is_ready():
            while root.dooneevent(_tkinter.ALL_EVENTS | _tkinter.DONT_WAIT):
                pass
            # Sleep to make the CPU idle, but not too long, so that the UI
            # stays responsive.
            time.sleep(0.01)

    if root is not None:
        if hasattr(root, "createfilehandler"):
            wait_using_filehandler()
        else:
            wait_using_polling()


def inputhook(inputhook_context: InputHookContext) -> None:
    # Only call the real input hook when the 'Tkinter' library was loaded.
    if "Tkinter" in sys.modules or "tkinter" in sys.modules:
        _inputhook_tk(inputhook_context)
