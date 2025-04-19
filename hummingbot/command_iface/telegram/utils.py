from hummingbot.command_iface.telegram.constants import TELEGRAM_MAX_MESSAGE_LENGTH


def split_message(message: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """
    Split long message into parts that fit Telegram message length limits

    :param message: Original message
    :param max_length: Maximum length of each part
    :return: List of message parts
    """
    # Split by newlines first to preserve formatting
    lines = message.split('\n')
    parts = []
    current_part = []
    current_length = 0

    for line in lines:
        line_length = len(line) + 1  # +1 for newline
        if current_length + line_length > max_length:
            if current_part:
                parts.append('\n'.join(current_part))
                current_part = []
                current_length = 0

            # Handle lines longer than max_length
            while len(line) > max_length:
                parts.append(line[:max_length])
                line = line[max_length:]

            if line:
                current_part = [line]
                current_length = len(line) + 1
        else:
            current_part.append(line)
            current_length += line_length

    if current_part:
        parts.append('\n'.join(current_part))

    return parts
