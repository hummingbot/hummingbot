TELEGRAM_POLL_TIMEOUT = 30
TELEGRAM_POLL_READ_TIMEOUT = 60
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


class MenuState:
    INSTANCE_SELECT = "instance_select"
    MAIN = "main"


CMD_SELECT_INSTANCE = "🔄 Select Instance"
CMD_STATUS = "📊 Status"
CMD_TICKER = "📈 Ticker"
CMD_BALANCE = "💰 Balance"
CMD_HISTORY = "📜 History"

COMMANDS_MAPPING = {
    CMD_STATUS: "status",
    CMD_TICKER: "ticker",
    CMD_BALANCE: "balance",
    CMD_HISTORY: "history",
}

MAIN_MENU = [
    [CMD_SELECT_INSTANCE],
    [CMD_STATUS, CMD_HISTORY],
    [CMD_BALANCE, CMD_TICKER],
]
