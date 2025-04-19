# Telegram polling settings
TELEGRAM_POLL_TIMEOUT = 30  # Timeout in seconds
TELEGRAM_POLL_READ_TIMEOUT = 60  # Read timeout in seconds

# Telegram message settings
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Telegram command settings
CMD_STATUS = '📊 Status'
CMD_TICKER = '📈 Ticker'
CMD_BALANCE = '💰 Balance'
CMD_HELP = '❓ Help'
CMD_START = '▶️ Start'
CMD_STOP = '⏹️ Stop'
CMD_HISTORY = '📜 History'
CMD_CONFIG = '⚙️ Config'
CMD_MORE = '📋 More commands'
CMD_BACK = '🔙 Back to main menu'

COMMANDS_MAPPING = {
    CMD_STATUS: 'status',
    CMD_TICKER: 'ticker',
    CMD_BALANCE: 'balance',
    CMD_HELP: 'help',
    CMD_START: 'start',
    CMD_STOP: 'stop',
    CMD_HISTORY: 'history',
    CMD_CONFIG: 'config',
}

MAIN_MENU = [
    [CMD_STATUS, CMD_HISTORY],
    [CMD_BALANCE, CMD_TICKER],
    [CMD_MORE]
]

ADDITIONAL_MENU = [
    [CMD_START, CMD_STOP],
    [CMD_CONFIG, CMD_HELP],
    [CMD_BACK]
]
