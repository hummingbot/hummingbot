"""hbot: an agent-friendly CLI to run, control, and monitor Hummingbot bots.

One process runs a single bot per instance. Bots are launched detached and controlled
through local files (pidfile + status snapshot) under ``data/instances/<name>/`` — no
external broker required. Trades and performance are read directly from each bot's sqlite DB.
"""
