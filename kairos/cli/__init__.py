"""hbot: an agent-friendly CLI to run, control, and monitor Kairos-2 bots.

One bot per install. The bot is launched detached and controlled through local files (pidfile +
status snapshot) under ``data/bot/`` — no external broker required. Trades and performance are read
directly from the bot's sqlite DB.
"""
