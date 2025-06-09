import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import pandas as pd

from .models import BotInstance, BrokerMessage, MessageStatus
from .storage import MessageStorage

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

logger = logging.getLogger(__name__)


class MessageBroker:
    def __init__(self, app: "HummingbotApplication"):
        self._app = app
        self._storage = MessageStorage()
        self._polling_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._poll_interval = app.client_config_map.telegram.polling_interval
        self._cleanup_interval = app.client_config_map.telegram.cleanup_interval
        self._message_retention_days = app.client_config_map.telegram.message_retention_days

    def get_formatted_instance_id(self) -> str:
        """Get a formatted instance ID for message routing that includes strategy file name"""
        instance_id = self._app.instance_id
        strategy_file = "default"
        if hasattr(self._app, "strategy_file_name") and self._app.strategy_file_name:
            strategy_file = self._app.strategy_file_name
        return f"{instance_id}|{strategy_file}"

    async def _register_current_instance(self) -> None:
        """Register this instance in the database for discovery"""
        try:
            # Get instance information
            instance_id = self._app.instance_id
            composite_id = self.get_formatted_instance_id()
            strategy_file = "default"
            if hasattr(self._app, "strategy_file_name") and self._app.strategy_file_name:
                strategy_file = self._app.strategy_file_name

            # Get strategy name if available
            strategy_name = None
            if hasattr(self._app, "strategy_name") and self._app.strategy_name:
                strategy_name = self._app.strategy_name

            # Get active markets
            markets = []
            if hasattr(self._app, "markets") and self._app.markets:
                markets = list(self._app.markets.keys())

            # Build description
            description_parts = []
            if strategy_name:
                description_parts.append(strategy_name)
            if markets:
                description_parts.append(f"@ {', '.join(markets)}")

            description = " | ".join(description_parts) if description_parts else None

            instance = BotInstance(
                composite_id=composite_id,
                instance_id=instance_id,
                strategy_file=strategy_file,
                strategy_name=strategy_name,
                markets=markets,
                description=description,
            )

            # Register in database
            await self._storage.register_instance(instance)
        except Exception as e:
            logger.error(f"Error registering instance: {e}", exc_info=True)

    async def start(self) -> None:
        """Start message polling and periodic cleanup"""
        if not self._is_running:
            try:
                self._is_running = True
                current_instance_id = self._app.instance_id

                # Register instance in the database
                await self._register_current_instance()

                # Start tasks
                self._polling_task = asyncio.create_task(self._poll_messages())
                self._cleanup_task = asyncio.create_task(self._cleanup_old_messages())

                logger.info(f"Message broker started for instance {current_instance_id} (poll interval: {self._poll_interval}s, "
                            f"cleanup interval: {self._cleanup_interval/3600:.1f}h, "
                            f"retention: {self._message_retention_days} days)")
            except Exception as e:
                self._is_running = False
                logger.error(f"Failed to start message broker: {e}", exc_info=True)
                raise

    async def stop(self) -> None:
        """Stop message polling and cleanup tasks"""
        self._is_running = False

        # Cancel polling task
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("Message broker stopped")

    async def _get_status_response(self) -> str:
        """Get formatted status response"""
        try:
            logger.info("Generating status response")
            if hasattr(self._app, "strategy") and self._app.strategy is not None:
                # Format basic info
                bot_id = self._app.instance_id
                strategy_name = self._app.strategy_name if hasattr(self._app, "strategy_name") else "Unknown"
                strategy_file = self._app.strategy_file_name if hasattr(self._app, "strategy_file_name") else "Unknown"
                status = "✅ Running" if self._app.strategy else "⏹️ Stopped"
                logger.debug(f"Status info: bot_id={bot_id}, strategy={strategy_name}, status={status}")

                # Format start time
                start_time = pd.Timestamp(self._app.start_time / 1e3, unit='s').strftime('%Y-%m-%d %H:%M:%S')
                uptime_seconds = int(time.time() - self._app.start_time / 1e3)
                hours, remainder = divmod(uptime_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = f"{hours}h {minutes}m {seconds}s"

                # Build market information
                market_info = []
                active_trading_pairs = []

                if hasattr(self._app, "markets") and self._app.markets:
                    for market_name, market in self._app.markets.items():
                        if not market:
                            continue

                        pairs_info = []
                        if hasattr(market, "trading_pairs"):
                            for pair in market.trading_pairs:
                                pairs_info.append(pair)
                                active_trading_pairs.append(f"{market_name}: {pair}")

                        if pairs_info:
                            market_info.append(f"{market_name} ({', '.join(pairs_info)})")
                        else:
                            market_info.append(market_name)

                # Build status response
                status_lines = [
                    f"Bot Status: {status}",
                    f"Instance ID: {bot_id}",
                    f"Strategy: {strategy_name}",
                    f"Config: {strategy_file}",
                    f"Started: {start_time}",
                    f"Uptime: {uptime}"
                ]

                if market_info:
                    status_lines.append(f"Markets: {', '.join(market_info)}")

                if active_trading_pairs:
                    status_lines.append("\nActive Trading Pairs:")
                    for pair in active_trading_pairs:
                        status_lines.append(f"   - {pair}")

                response = "\n".join(status_lines)
                logger.info(f"Generated status response ({len(response)} chars)")
                return response
            else:
                logger.info("No strategy running, returning empty status")
                return "No strategy running"
        except Exception as e:
            logger.error(f"Error getting status: {e}", exc_info=True)
            return f"Error getting status: {str(e)}"

    async def _get_balance_response(self) -> str:
        """Get formatted balance response"""
        try:
            logger.info("Generating balance response")
            if hasattr(self._app, "markets") and self._app.markets:
                # Get basic bot information
                instance_id = self._app.instance_id
                strategy_name = self._app.strategy_name if hasattr(self._app, "strategy_name") else "Unknown"

                balance_text = f"💰 Balances for [{strategy_name}]\n"
                balance_text += f"Instance: {instance_id}\n\n"

                # Track total balance in USD if possible
                total_value_usd = 0.0
                has_usd_values = False

                # Track how many markets we processed
                markets_count = 0
                markets_with_balance = 0

                for market_name, market in self._app.markets.items():
                    if not market:
                        continue

                    markets_count += 1
                    logger.debug(f"Getting balance for market: {market_name}")

                    try:
                        # Try different methods to get balance
                        balances = {}

                        # Method 1: get_all_balances
                        if hasattr(market, "get_all_balances"):
                            try:
                                logger.debug(f"Trying get_all_balances for {market_name}")
                                balances = await market.get_all_balances()
                                if balances:
                                    logger.debug(f"get_all_balances succeeded for {market_name}")
                            except Exception as e:
                                logger.debug(f"get_all_balances failed for {market_name}: {e}")

                        # Method 2: get_all_account_balances
                        if not balances and hasattr(market, "get_all_account_balances"):
                            try:
                                logger.debug(f"Trying get_all_account_balances for {market_name}")
                                balances = await market.get_all_account_balances()
                                if balances:
                                    logger.debug(f"get_all_account_balances succeeded for {market_name}")
                            except Exception as e:
                                logger.debug(f"get_all_account_balances failed for {market_name}: {e}")

                        # Method 3: get_account_balances
                        if not balances and hasattr(market, "get_account_balances"):
                            try:
                                logger.debug(f"Trying get_account_balances for {market_name}")
                                balances = await market.get_account_balances()
                                if balances:
                                    logger.debug(f"get_account_balances succeeded for {market_name}")
                            except Exception as e:
                                logger.debug(f"get_account_balances failed for {market_name}: {e}")

                        # Method 4: balance
                        if not balances and hasattr(market, "balance"):
                            try:
                                logger.debug(f"Trying balance attribute for {market_name}")
                                balances = market.balance
                                if balances:
                                    logger.debug(f"balance attribute succeeded for {market_name}")
                            except Exception as e:
                                logger.debug(f"accessing balance attribute failed for {market_name}: {e}")

                        # Method 5: available_balances
                        if not balances and hasattr(market, "available_balances"):
                            try:
                                logger.debug(f"Trying available_balances attribute for {market_name}")
                                balances = market.available_balances
                                if balances:
                                    logger.debug(f"available_balances attribute succeeded for {market_name}")
                            except Exception as e:
                                logger.debug(f"accessing available_balances attribute failed for {market_name}: {e}")

                        if balances:
                            # Group balances with non-zero amounts
                            non_zero_balances = {}
                            for asset, amount in balances.items():
                                try:
                                    amount_float = float(amount)
                                    if amount_float > 0:
                                        # Format the amount to not show excessive decimal places
                                        if amount_float < 0.0001:
                                            formatted_amount = f"{amount_float:.8f}"
                                        elif amount_float < 0.01:
                                            formatted_amount = f"{amount_float:.6f}"
                                        else:
                                            formatted_amount = f"{amount_float:.4f}"
                                        non_zero_balances[asset] = formatted_amount
                                except (ValueError, TypeError):
                                    # In case amount is not a valid number
                                    non_zero_balances[asset] = amount

                            if non_zero_balances:
                                markets_with_balance += 1
                                balance_text += f"📊 {market_name}:\n"
                                for asset, amount in non_zero_balances.items():
                                    balance_text += f"   {asset}: {amount}\n"
                                logger.debug(f"Added {len(non_zero_balances)} non-zero balances for {market_name}")
                            else:
                                balance_text += f"📊 {market_name}: No non-zero balances\n"
                                logger.debug(f"No non-zero balances found for {market_name}")
                        else:
                            balance_text += f"📊 {market_name}: No balance data available\n"
                            logger.debug(f"No balance data available for {market_name}")
                    except Exception as e:
                        logger.error(f"Error getting balance for {market_name}: {e}", exc_info=True)
                        balance_text += f"📊 {market_name}: Error getting balance\n"

                # Add total value if available
                if has_usd_values:
                    balance_text += f"\nTotal value: ~${total_value_usd:.2f} USD"

                logger.info(f"Generated balance response for {markets_with_balance}/{markets_count} markets with balances")
                return balance_text
            else:
                logger.info("No active markets for balance response")
                return "No active markets or balances available"
        except Exception as e:
            logger.error(f"Error getting balances: {e}", exc_info=True)
            return f"Error getting balances: {str(e)}"

    async def _get_history_response(self) -> str:
        """Get trade history response"""
        try:
            logger.info("Generating trade history response")
            if hasattr(self._app, "markets_recorder") and self._app.markets_recorder:
                # Get basic bot information
                instance_id = self._app.instance_id
                strategy_name = self._app.strategy_name if hasattr(self._app, "strategy_name") else "Unknown"
                strategy_file = self._app.strategy_file_name if hasattr(self._app, "strategy_file_name") else "Unknown"

                limit = 10  # Limit to last 10 trades
                logger.debug(f"Retrieving up to {limit} trades for strategy file: {strategy_file}")

                try:
                    trades = self._app.markets_recorder.get_trades_for_config(strategy_file, limit)
                    logger.info(f"Retrieved {len(trades) if trades else 0} trades from recorder")
                except Exception as e:
                    logger.error(f"Error retrieving trades from recorder: {e}", exc_info=True)
                    trades = []

                header = f"📜 Trade History for [{strategy_name}]\n"
                header += f"Instance: {instance_id}\n"

                if trades and len(trades) > 0:
                    trade_list = []
                    logger.debug(f"Formatting {len(trades)} trades")
                    for trade in trades:
                        try:
                            # Format the trade data nicely
                            trade_time = pd.Timestamp(int(trade.timestamp / 1e3), unit='s').strftime('%Y-%m-%d %H:%M:%S')
                            market = trade.market
                            trade_type = "BUY" if trade.trade_type.lower() == "buy" else "SELL"
                            trade_type_emoji = "🟢" if trade_type == "BUY" else "🔴"

                            # Format price with appropriate decimal places
                            price = float(trade.price)
                            if price < 0.0001:
                                price_str = f"{price:.8f}"
                            elif price < 0.01:
                                price_str = f"{price:.6f}"
                            else:
                                price_str = f"{price:.4f}"

                            # Format trade info
                            trade_info = (f"{trade_type_emoji} {trade_time} | "
                                          f"{market} | "
                                          f"{trade_type} {trade.amount} {trade.base_asset} @ "
                                          f"{price_str} {trade.quote_asset}")

                            trade_list.append(trade_info)
                        except Exception as e:
                            logger.error(f"Error formatting trade: {e}", exc_info=True)
                            trade_list.append(f"Error formatting trade record: {str(e)}")

                    response = header + "\n" + "\n".join(trade_list)
                    logger.info(f"Generated trade history with {len(trade_list)} trades")
                    return response
                else:
                    logger.info("No trade history found")
                    return header + "\nNo recent trade history"
            else:
                logger.info("Markets recorder not available")
                return "Trade history not available - markets recorder not initialized"
        except Exception as e:
            logger.error(f"Error getting trade history: {e}", exc_info=True)
            return f"Error retrieving trade history: {str(e)}"

    async def _get_ticker_response(self) -> str:
        """Get market ticker information"""
        try:
            logger.info("Generating ticker response")
            if not hasattr(self._app, "markets") or not self._app.markets:
                logger.info("No active markets for ticker response")
                return "No active markets"

            ticker_data = []
            markets_count = 0
            successful_pairs = 0

            for market_name, market in self._app.markets.items():
                if not market:
                    continue

                markets_count += 1
                logger.debug(f"Getting ticker information for market: {market_name}")

                try:
                    # Different connectors may have different methods to get trading pairs
                    trading_pairs = []
                    if hasattr(market, "trading_pairs"):
                        logger.debug(f"Getting trading pairs from trading_pairs attribute for {market_name}")
                        trading_pairs = market.trading_pairs
                    elif hasattr(market, "get_trading_pairs"):
                        logger.debug(f"Getting trading pairs from get_trading_pairs() for {market_name}")
                        trading_pairs = await market.get_trading_pairs()

                    if not trading_pairs:
                        logger.debug(f"No trading pairs found for {market_name}")
                        ticker_data.append(f"{market_name}: No trading pairs available")
                        continue

                    logger.debug(f"Found {len(trading_pairs)} trading pairs for {market_name}")

                    for trading_pair in trading_pairs:
                        try:
                            logger.debug(f"Getting ticker information for {market_name} {trading_pair}")
                            # Try different methods to get ticker data
                            ticker_info = None

                            # Method 1: get_ticker
                            if hasattr(market, "get_ticker"):
                                logger.debug(f"Trying get_ticker for {market_name} {trading_pair}")
                                try:
                                    ticker = await market.get_ticker(trading_pair)
                                    if ticker and hasattr(ticker, "bid") and hasattr(ticker, "ask"):
                                        bid = getattr(ticker, "bid", 0)
                                        ask = getattr(ticker, "ask", 0)
                                        mid = (bid + ask) / 2 if bid and ask else 0
                                        ticker_info = (
                                            f"{market_name} {trading_pair}:\n"
                                            f"- bid: {bid:.8g}\n"
                                            f"- ask: {ask:.8g}\n"
                                            f"- mid: {mid:.8g}"
                                        )
                                        logger.debug(f"get_ticker successful for {market_name} {trading_pair}")
                                except Exception as e:
                                    logger.debug(f"get_ticker failed for {market_name} {trading_pair}: {e}")

                            # Method 2: get_price_by_type
                            if not ticker_info and hasattr(market, "get_price_by_type"):
                                logger.debug(f"Trying get_price_by_type for {market_name} {trading_pair}")
                                try:
                                    bid = await market.get_price_by_type(trading_pair, "bid")
                                    ask = await market.get_price_by_type(trading_pair, "ask")
                                    mid = await market.get_price_by_type(trading_pair, "mid")
                                    if any([bid, ask, mid]):
                                        ticker_info = (
                                            f"{market_name} {trading_pair}:\n"
                                            f"- bid: {bid:.8g if bid else 'N/A'}\n"
                                            f"- ask: {ask:.8g if ask else 'N/A'}\n"
                                            f"- mid: {mid:.8g if mid else 'N/A'}"
                                        )
                                        logger.debug(f"get_price_by_type successful for {market_name} {trading_pair}")
                                except Exception as e:
                                    logger.debug(f"get_price_by_type failed for {market_name} {trading_pair}: {e}")

                            # Method 3: get_price
                            if not ticker_info and hasattr(market, "get_price"):
                                logger.debug(f"Trying get_price for {market_name} {trading_pair}")
                                try:
                                    price = await market.get_price(trading_pair)
                                    if price:
                                        ticker_info = f"{market_name} {trading_pair}: {price:.8g}"
                                        logger.debug(f"get_price successful for {market_name} {trading_pair}")
                                except Exception as e:
                                    logger.debug(f"get_price failed for {market_name} {trading_pair}: {e}")

                            if ticker_info:
                                ticker_data.append(ticker_info)
                                successful_pairs += 1
                            else:
                                ticker_data.append(f"{market_name} {trading_pair}: Price data not available")
                                logger.debug(f"No ticker information available for {market_name} {trading_pair}")

                        except Exception as e:
                            logger.error(f"Error getting ticker for {market_name} {trading_pair}: {e}")
                            ticker_data.append(f"{market_name} {trading_pair}: Error getting ticker")
                except Exception as e:
                    logger.error(f"Error processing market {market_name}: {e}")
                    ticker_data.append(f"{market_name}: Error getting ticker data")

            logger.info(f"Generated ticker information for {successful_pairs} trading pairs from {markets_count} markets")

            if ticker_data:
                return "Ticker Information:\n\n" + "\n\n".join(ticker_data)
            else:
                return "No ticker data available"
        except Exception as e:
            logger.error(f"Error getting ticker information: {e}", exc_info=True)
            return f"Error retrieving ticker information: {str(e)}"

    async def _cleanup_old_messages(self) -> None:
        """Periodically clean up old messages"""
        while self._is_running:
            try:
                # Run cleanup on schedule
                current_instance_id = self._app.instance_id
                logger.debug(f"Running scheduled cleanup of messages older than {self._message_retention_days} days for instance {current_instance_id}")

                cleanup_start_time = time.time()
                deleted_count = await self._storage.purge_old_messages(self._message_retention_days)
                cleanup_duration = time.time() - cleanup_start_time

                if deleted_count > 0:
                    logger.info(f"Cleanup deleted {deleted_count} old messages in {cleanup_duration:.2f}s")
                else:
                    logger.debug(f"No old messages to delete (checked in {cleanup_duration:.2f}s)")

                # Sleep for the cleanup interval
                await asyncio.sleep(self._cleanup_interval)
            except asyncio.CancelledError:
                logger.info("Message cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message cleanup: {str(e)}", exc_info=True)
                # Use shorter sleep interval on error to prevent long service disruption
                await asyncio.sleep(60)  # Sleep for a minute before retrying

    async def process_message(self, raw_message: str, source: str, chat_id: str) -> Optional[int]:
        """Process incoming message and return the message ID if successful"""
        try:
            # Validate message format
            if ':' not in raw_message:
                logger.error(f"Invalid message format (missing ':'): {raw_message}")
                return None

            # Format should now be: "instanceId|strategyFile:command"
            composite_id, command = raw_message.split(':', 1)

            if not command.strip():
                logger.error(f"Empty command received for instance {composite_id}")
                return None

            # Make sure composite_id has the right format
            if "|" not in composite_id:
                logger.warning(f"Composite ID '{composite_id}' is missing strategy part, adding default")
                composite_id = f"{composite_id}|default"

            # Current instance information with strategy
            current_composite_id = self.get_formatted_instance_id()
            logger.debug(f"Current composite ID: {current_composite_id}, Target composite ID: {composite_id}")

            # Log command received
            logger.info(f"Received command '{command.strip()}' for instance '{composite_id}' (current instance: '{current_composite_id}') from {source}")
            logger.debug(f"Full message details - raw: '{raw_message}', source: '{source}', chat_id: '{chat_id}'")
            logger.debug(f"Message details - source: {source}, chat_id: {chat_id}")

            now = datetime.utcnow()
            message = BrokerMessage(
                id=None,
                instance_id=composite_id,  # Store the full composite ID
                strategy_name="",  # No longer needed as it's part of the composite ID
                command=command.strip(),
                source=source,
                chat_id=chat_id,
                status=MessageStatus.NEW,
                created_at=now,
                updated_at=now,
                response=None,
                error=None
            )

            message_id = await self._storage.save_message(message)
            logger.info(f"Saved new message ID {message_id} from {source}: '{command.strip()}'")

            # Start broker if not already running
            if not self._is_running or not self._polling_task:
                logger.info(f"Starting broker to process message ID {message_id}")
                await self.start()
            else:
                logger.debug(f"Broker already running, will process message ID {message_id} in next poll cycle")

            return message_id

        except ValueError as e:
            logger.error(f"Invalid message format: {raw_message}, error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return None

    async def _poll_messages(self) -> None:
        """Poll and process messages"""
        while self._is_running:
            try:
                # Get current instance ID with strategy file as a composite ID
                current_composite_id = self.get_formatted_instance_id()

                # Get all pending messages - we'll filter for our composite instance ID in the processing loop
                messages = await self._storage.get_pending_messages()

                if messages:
                    logger.info(f"Found {len(messages)} pending messages to check (current instance: '{current_composite_id}')")
                    for idx, msg in enumerate(messages, 1):
                        logger.info(f"  Message {idx}: ID {msg.id}, Command: '{msg.command}', Target instance: '{msg.instance_id}'")

                # Process each message
                processed_count = 0
                for message in messages:
                    try:
                        message_id = message.id
                        command = message.command.strip()
                        target_composite_id = message.instance_id

                        logger.debug(f"Examining message {message_id}: target='{target_composite_id}', command='{command}'")

                        # Verify this is the correct instance to handle the message
                        if target_composite_id != current_composite_id:
                            logger.debug(f"Skipping message {message_id}: targeted for instance '{target_composite_id}', current instance is '{current_composite_id}'")
                            continue

                        # We found a message for this instance - process it
                        processed_count += 1
                        logger.info(f"Processing message ID {message_id} with command '{command}' for this instance '{current_composite_id}'")

                        # Mark as processing since this is the correct instance
                        await self._storage.update_message_status(
                            message_id,
                            MessageStatus.PROCESSING
                        )

                        # Execute the command and get response
                        self._app.app.clear_input()
                        response_start_time = time.time()

                        # Special handling for common commands that return output
                        response = None
                        if command == "status":
                            logger.debug(f"Executing 'status' command for message {message_id}")
                            response = await self._get_status_response()
                        elif command == "history":
                            logger.debug(f"Executing 'history' command for message {message_id}")
                            response = await self._get_history_response()
                        elif command == "balance":
                            logger.debug(f"Executing 'balance' command for message {message_id}")
                            response = await self._get_balance_response()
                        elif command == "ticker":
                            logger.debug(f"Executing 'ticker' command for message {message_id}")
                            response = await self._get_ticker_response()
                        else:
                            # For other commands, can't directly execute
                            response = f"Command '{command}' not supported via messaging"
                            logger.warning(f"Unsupported command '{command}' for message {message_id}")

                        processing_time = time.time() - response_start_time
                        response_length = len(response) if response else 0
                        logger.info(f"Command '{command}' execution completed in {processing_time:.2f}s (response length: {response_length} chars)")

                        # Update message status with response
                        if response:
                            if len(response) > 100:
                                logger.debug(f"Response preview: {response[:100]}...")
                            else:
                                logger.debug(f"Response: {response}")
                        else:
                            logger.warning(f"No response generated for message {message_id} with command '{command}'")
                            response = "Command completed but generated no output"

                        await self._storage.update_message_status(
                            message_id,
                            MessageStatus.COMPLETED,
                            response=response
                        )
                        logger.debug(f"Response summary for message ID {message_id}: {response[:50]}{'...' if response and len(response) > 50 else ''}")
                    except asyncio.CancelledError:
                        logger.warning(f"Processing of message ID {message.id} was cancelled")
                        raise
                    except Exception as e:
                        logger.error(f"❌ Error processing message ID {message.id}: {str(e)}", exc_info=True)
                        error_message = f"{type(e).__name__}: {str(e)}"
                        logger.error(f"Setting message {message.id} to FAILED status with error: {error_message}")
                        await self._storage.update_message_status(
                            message.id,
                            MessageStatus.FAILED,
                            error=error_message
                        )

                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                logger.info("Message polling task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message polling: {str(e)}", exc_info=True)
                await asyncio.sleep(self._poll_interval)
