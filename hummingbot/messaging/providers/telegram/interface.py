import asyncio
import logging
from typing import Dict, List, Optional

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ...base.broker import MessageBroker
from ...base.models import MessageStatus
from ...utils import format_composite_id_for_display
from .constants import (
    CMD_SELECT_INSTANCE,
    COMMANDS_MAPPING,
    MAIN_MENU,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    TELEGRAM_POLL_READ_TIMEOUT,
    TELEGRAM_POLL_TIMEOUT,
    MenuState,
)

logger = logging.getLogger(__name__)


def _split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH - 200) -> List[str]:
    """Split a long message into smaller chunks that fit within Telegram's message size limit"""
    chunks = []
    current_chunk = ""

    lines = text.split('\n')

    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            if len(line) > max_length:
                while line:
                    chunks.append(line[:max_length])
                    line = line[max_length:]
            else:
                current_chunk = line
        else:
            if current_chunk:
                current_chunk += "\n" + line
            else:
                current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def _get_available_instances() -> List[str]:
    """Get list of available instances from the central registry"""
    try:
        logger.info("Requesting available Hummingbot instances from central registry")

        # Get broker from the current bot instance to access storage
        from hummingbot.client.hummingbot_application import HummingbotApplication
        main_app = HummingbotApplication.main_application()
        instances = []

        # Get the message broker to access storage
        broker = None
        if main_app and hasattr(main_app, '_message_broker'):
            broker = main_app._message_broker

        if not broker:
            logger.warning("No message broker available to access instance registry")
            return ["default"]

        # Get all registered instances from the database
        registered_instances = await broker._storage.get_all_instances()
        logger.info(f"Found {len(registered_instances)} registered instances in the database")

        # Format each instance for display
        for instance in registered_instances:
            # Use the composite ID for internal routing
            composite_id = instance.composite_id

            # Build the display text with descriptive information
            if instance.description:
                instance_display = f"{composite_id} ({instance.description})"
            else:
                # Build a description based on available information
                description_parts = []
                if instance.strategy_name:
                    description_parts.append(instance.strategy_name)
                if instance.strategy_file and instance.strategy_file != instance.strategy_name:
                    description_parts.append(f"file: {instance.strategy_file}")
                if instance.markets:
                    description_parts.append(f"@ {', '.join(instance.markets)}")

                if description_parts:
                    instance_display = f"{composite_id} ({' | '.join(description_parts)})"
                else:
                    instance_display = composite_id

            instances.append(instance_display)
            logger.debug(f"Added instance to selection list: {instance_display}")

        if instances:
            return instances
        else:
            logger.warning("No instances found in registry")
            return ["default"]

    except Exception as e:
        logger.error(f"Error getting available instances from registry: {e}", exc_info=True)
        return ["default"]


class TelegramMessenger:
    def __init__(self, token: str, chat_id: str, broker: MessageBroker):
        self._token = token
        self._chat_id = chat_id
        self._broker = broker
        self._application: Optional[Application] = None
        self._telegram_task: Optional[asyncio.Task] = None
        self._menu_state = MenuState.INSTANCE_SELECT
        self._current_instance: Optional[str] = None
        self._user_instances: Dict[str, str] = {}  # chat_id -> instance_id
        self._response_check_task: Optional[asyncio.Task] = None
        self._update_instances_task: Optional[asyncio.Task] = None
        self._message_cache: Dict[int, str] = {}  # message_id -> chat_id
        self._is_running = False
        self._available_instances: List[str] = []
        self._instances_update_interval = 30.0  # Update instances list every 30 seconds

    def _is_authorized(self, update: Update) -> bool:
        """Check if the user is authorized to use this bot"""
        if not update.effective_chat:
            logger.warning("Received update without chat information")
            return False

        is_authorized = str(update.effective_chat.id) == self._chat_id
        if not is_authorized:
            logger.warning(f"Unauthorized access attempt from chat ID: {update.effective_chat.id} (authorized: {self._chat_id})")

        return is_authorized

    async def _handle_message(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages"""
        try:
            if not update.effective_chat:
                logger.warning("Message received without an effective chat")
                return

            if not self._is_authorized(update):
                logger.warning(f"Unauthorized access attempt from: {update.effective_chat.id}")
                await update.message.reply_text("Unauthorized access")
                return

            chat_id = str(update.effective_chat.id)
            text = update.message.text

            logger.debug(f"Received message: '{text}' from chat_id: {chat_id}")

            if text == CMD_SELECT_INSTANCE:
                self._menu_state = MenuState.INSTANCE_SELECT
                self._available_instances = await _get_available_instances()
                keyboard = [[instance] for instance in self._available_instances] if self._available_instances else [["No instances available"]]
                await update.message.reply_text(
                    "Select instance:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                logger.debug(f"Showed instance selection menu with {len(self._available_instances)} instances")
                return

            if self._menu_state == MenuState.INSTANCE_SELECT:
                # Extract the full composite ID from the display text (format: "instance_id|strategy_file (info)")
                instance_parts = text.split(" (", 1)
                composite_id = instance_parts[0].strip()

                # Store the complete composite ID for message routing
                self._user_instances[chat_id] = composite_id

                # Format for display
                display_id = format_composite_id_for_display(composite_id)

                # Get a friendly display name for the notification
                display_name = text
                if len(instance_parts) > 1:
                    display_name = f"{display_id} ({instance_parts[1]}"

                self._menu_state = MenuState.MAIN
                await update.message.reply_text(
                    f"Instance selected: {display_name}",
                    reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
                )
                return

            if chat_id not in self._user_instances:
                await update.message.reply_text("Please select an instance first",
                                                reply_markup=ReplyKeyboardMarkup([[CMD_SELECT_INSTANCE]], resize_keyboard=True))
                logger.warning(f"User {chat_id} attempted to send command without selecting instance")
                return

            instance_id = self._user_instances[chat_id]
            command = COMMANDS_MAPPING.get(text)
            if command:
                message = f"{instance_id}:{command}"
                display_id = format_composite_id_for_display(instance_id)
                await update.message.reply_text(f"Sending command '{command}' to instance '{display_id}'...")

                # Store message in broker
                logger.debug(f"Sending raw message to broker: '{message}'")
                message_id = await self._broker.process_message(
                    message,
                    source="telegram",
                    chat_id=chat_id
                )

                if message_id:
                    self._message_cache[message_id] = chat_id
                else:
                    logger.error(f"Failed to queue command '{command}' for instance '{instance_id}'")
                    await update.message.reply_text(
                        f"⚠️ Command '{command}' could not be processed. Please try again."
                    )
            else:
                logger.debug(f"Unknown command: {text}")
                await update.message.reply_text(
                    "Unknown command. Please use the menu buttons.",
                    reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
                )
        except Exception as e:
            logger.error(f"Error handling telegram message: {e}", exc_info=True)
            await update.message.reply_text("An error occurred while processing your request.")

    async def _check_for_responses(self) -> None:
        """Check for completed messages and send responses to Telegram"""
        while self._is_running:
            try:
                messages = await self._get_completed_messages()

                for message_id, status, response, error in messages:
                    chat_id = self._message_cache.get(message_id)
                    if chat_id:
                        try:
                            await self._send_response_to_telegram(chat_id, status, response, error)
                            await self._broker._storage.delete_message(message_id)
                            self._message_cache.pop(message_id, None)

                        except Exception as e:
                            logger.error(f"Error sending response for message {message_id}: {e}", exc_info=True)
                            # Keep the message in cache for retry on next cycle if there was an error
                    else:
                        logger.warning(f"Received completed message {message_id} but no chat_id found in cache")

                # Sleep between checks (use a smaller interval for more responsive updates)
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                logger.info("Response checking task cancelled")
                break
            except Exception as e:
                logger.error(f"Error checking for responses: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _get_completed_messages(self) -> List[tuple]:
        """Get messages that have been completed or failed"""
        from hummingbot.messaging.base.models import MessageStatus
        try:
            completed = await self._broker._storage.get_completed_messages()
            logger.debug(f"Retrieved {len(completed)} completed/failed messages from database")

            # Only return messages that are in our cache and have been processed
            result = []
            for msg in completed:
                if msg.id in self._message_cache:
                    if msg.status == MessageStatus.COMPLETED or msg.status == MessageStatus.FAILED:
                        logger.debug(f"Found valid completed message ID {msg.id} with status {msg.status.value}, command: {msg.command}")
                        result.append((msg.id, msg.status, msg.response, msg.error))
                    else:
                        logger.debug(f"Message {msg.id} in cache but status is {msg.status.value}, not ready for processing")

            return result
        except Exception as e:
            logger.error(f"Error getting completed messages: {e}", exc_info=True)
            return []

    async def _send_response_to_telegram(self, chat_id: str, status: MessageStatus,
                                         response: Optional[str], error: Optional[str]) -> None:
        """Send command response back to Telegram"""
        if not self._application or not self._application.bot:
            logger.error("Cannot send response: Telegram bot not initialized")
            return

        try:
            logger.debug(f"Preparing to send {status.value} response to chat {chat_id}")

            # Create appropriate message based on status
            if status == MessageStatus.COMPLETED:
                if response:
                    logger.debug(f"Sending response with length {len(response)}")
                    # Format long responses nicely
                    if len(response) > TELEGRAM_MAX_MESSAGE_LENGTH - 100:
                        # Split long messages
                        chunks = _split_message(response)
                        logger.info(f"Sending response in {len(chunks)} chunks")

                        for i, chunk in enumerate(chunks):
                            header = f"Response part {i+1}/{len(chunks)}:\n" if len(chunks) > 1 else ""
                            try:
                                await self._application.bot.send_message(
                                    chat_id=int(chat_id),
                                    text=f"{header}{chunk}"
                                )
                                logger.debug(f"Sent chunk {i+1}/{len(chunks)} successfully")
                            except Exception as chunk_error:
                                logger.error(f"Error sending chunk {i+1}/{len(chunks)}: {chunk_error}")
                    else:
                        await self._application.bot.send_message(
                            chat_id=int(chat_id),
                            text=response
                        )
                        logger.debug("Sent single message response successfully")
                else:
                    logger.debug("No response content, sending success message")
                    await self._application.bot.send_message(
                        chat_id=int(chat_id),
                        text="✅ Command executed successfully (no output)"
                    )
            else:  # FAILED or other states
                error_text = error if error else "Unknown error"
                logger.debug(f"Sending error response: {error_text}")
                await self._application.bot.send_message(
                    chat_id=int(chat_id),
                    text=f"❌ Error executing command: {error_text}"
                )

            # Send a keyboard reminder after sending the response
            await asyncio.sleep(0.5)  # Small delay between messages
            await self._application.bot.send_message(
                chat_id=int(chat_id),
                text="Use the keyboard below for more commands:",
                reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
            )

        except Exception as e:
            logger.error(f"Error sending response to Telegram: {e}", exc_info=True)
            raise  # Re-raise to ensure the calling code knows there was a problem

    async def _update_instances_periodically(self) -> None:
        """Periodically update the list of available instances from central registry"""
        while self._is_running:
            try:
                # Update instances first before waiting
                try:
                    self._available_instances = await _get_available_instances()
                    logger.info(f"Updated available instances from registry, found {len(self._available_instances)} instance(s)")
                    for i, instance in enumerate(self._available_instances):
                        logger.debug(f"  Instance {i+1}: {instance}")
                except Exception as e:
                    logger.error(f"Error updating instances list from registry: {e}", exc_info=True)

                # Use a shorter interval for more responsive updates
                # This ensures users see new instances quickly
                await asyncio.sleep(self._instances_update_interval)
            except asyncio.CancelledError:
                logger.info("Instance update task cancelled")
                break
            except Exception as e:
                logger.error(f"Error updating instances: {e}", exc_info=True)
                await asyncio.sleep(10)  # Shorter interval on error

    async def start(self) -> None:
        """Start the Telegram interface"""
        if not self._token:
            logger.error("Telegram token not provided. Cannot start Telegram messenger.")
            return

        try:
            self._application = Application.builder() \
                .token(self._token) \
                .read_timeout(TELEGRAM_POLL_READ_TIMEOUT) \
                .connect_timeout(TELEGRAM_POLL_TIMEOUT) \
                .build()

            self._application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )

            await self._application.initialize()
            await self._application.start()
            await self._application.updater.start_polling()

            # Start background tasks
            self._is_running = True
            self._response_check_task = asyncio.create_task(self._check_for_responses())
            self._update_instances_task = asyncio.create_task(self._update_instances_periodically())

            # Initial instance fetch
            self._available_instances = await _get_available_instances()

            # Send welcome message to the specified chat_id
            if self._chat_id:
                try:
                    # Get instance info for the welcome message
                    instance_info = "\n".join(f"- {instance}" for instance in self._available_instances) if self._available_instances else "No active bots"

                    welcome_message = (
                        "Telegram messenger connected and ready to receive commands!\n\n"
                        f"Active Hummingbot instances:\n{instance_info}\n\n"
                        "Please use the 'Select Instance' button to choose a bot."
                    )

                    await self._application.bot.send_message(
                        chat_id=int(self._chat_id),
                        text=welcome_message,
                        reply_markup=ReplyKeyboardMarkup([[CMD_SELECT_INSTANCE]], resize_keyboard=True)
                    )
                except Exception as e:
                    logger.error(f"Error sending welcome message: {e}")

            logger.info("Telegram messenger started successfully")
        except Exception as e:
            logger.error(f"Failed to start Telegram messenger: {e}", exc_info=True)

    async def stop(self) -> None:
        """Stop the Telegram interface"""
        try:
            self._is_running = False

            # Stop response checking task
            if self._response_check_task:
                self._response_check_task.cancel()
                try:
                    await self._response_check_task
                except asyncio.CancelledError:
                    pass
                self._response_check_task = None

            # Stop instances update task
            if self._update_instances_task:
                self._update_instances_task.cancel()
                try:
                    await self._update_instances_task
                except asyncio.CancelledError:
                    pass
                self._update_instances_task = None

            # Stop Telegram application
            if self._application:
                if self._application.updater and self._application.updater.running:
                    await self._application.updater.stop()
                if self._application.running:
                    await self._application.stop()

                logger.info("Telegram messenger stopped")
            else:
                logger.debug("Telegram messenger already stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram messenger: {e}", exc_info=True)
