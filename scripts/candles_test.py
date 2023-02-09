from typing import Dict

import numpy as np
import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SignalFactory:
    def __init__(self, max_records: int, connectors: Dict[str, ConnectorBase], interval: str = "1m"):
        self.connectors = connectors
        self.candles = {
            connector_name: {trading_pair: CandlesFactory.get_candle(connector="binance_spot",
                                                                     trading_pair=trading_pair,
                                                                     interval=interval, max_records=max_records)
                             for trading_pair in connector.trading_pairs} for
            connector_name, connector in self.connectors.items()}

    def stop(self):
        for connector_name, trading_pairs_candles in self.candles.items():
            for candles in trading_pairs_candles.values():
                candles.stop()

    def start(self):
        for connector_name, trading_pairs_candles in self.candles.items():
            for candles in trading_pairs_candles.values():
                candles.start()

    @property
    def all_data_sources_ready(self):
        return all(np.array([[candles.is_ready for trading_pair, candles in trading_pairs_candles.items()]
                             for connector_name, trading_pairs_candles in self.candles.items()]).flatten())

    def candles_df(self):
        return {connector_name: {trading_pair: candles.candles for trading_pair, candles in
                trading_pairs_candles.items()}
                for connector_name, trading_pairs_candles in self.candles.items()}

    def features_df(self):
        candles_df = self.candles_df().copy()
        for connector_name, trading_pairs_candles in candles_df.items():
            for trading_pair, candles in trading_pairs_candles.items():
                candles.ta.rsi(length=14, append=True)
        return candles_df

    def current_features(self):
        return {connector_name: {trading_pair: features.iloc[-1, :].to_dict() for trading_pair, features in
                                 trading_pairs_features.items()}
                for connector_name, trading_pairs_features in self.features_df().items()}


class DirectionalStrategyPerpetuals(ScriptStrategyBase):
    max_executors_by_connector_trading_pair = 1
    trading_pairs = ["ETH-USDT", "BTC-USDT"]
    exchange = "binance_paper_trade"
    markets = {exchange: set(trading_pairs)}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.signal_factory = None

    def on_tick(self):
        if not self.signal_factory:
            self.signal_factory = SignalFactory(max_records=1000, connectors=self.connectors, interval="3d")
            self.signal_factory.start()

    def on_stop(self):
        # TODO: add to the stop command the ability to code a custom stop when calling the command
        self.signal_factory.stop()

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        if self.signal_factory and self.signal_factory.all_data_sources_ready:
            lines.extend(["\n############################################ Market Data ############################################"])
            for connector_name, trading_pair_signal in self.signal_factory.candles_df().items():
                for trading_pair, candles in trading_pair_signal.items():
                    candles["timestamp"] = pd.to_datetime(candles["timestamp"], unit="ms")
                    lines.extend([f"| Trading Pair: {trading_pair} | Exchange: {connector_name}"])
                    lines.extend(["    " + line for line in candles.tail().to_string(index=False).split("\n")])
                    lines.extend(["\n-----------------------------------------------------------------------------------------------------------"])

        else:
            lines.extend(["", "  No data collected."])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
