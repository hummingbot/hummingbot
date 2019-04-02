#!/usr/bin/env python

import asyncio
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.clipboard import ClipboardData
from prompt_toolkit.document import Document


def load_key_bindings(hb) -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add('c-c')
    def _(event):
        hb.app.log("\n[CTRL + C] keyboard exit")
        asyncio.ensure_future(hb.exit())

    return bindings
