"""
Focused coverage tests for model __repr__, query, and to_pandas methods.
Targets uncovered lines identified by diff-cover.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture(scope="module")
def db_engine():
    """Create an in-memory SQLite engine with all ORM tables."""
    from hummingbot.model import HummingbotBase

    # Import all models so they register with HummingbotBase.metadata
    from hummingbot.model.funding_payment import FundingPayment  # noqa: F401
    from hummingbot.model.market_data import MarketData  # noqa: F401
    from hummingbot.model.market_state import MarketState  # noqa: F401
    from hummingbot.model.order import Order  # noqa: F401
    from hummingbot.model.order_status import OrderStatus  # noqa: F401
    from hummingbot.model.position import Position  # noqa: F401
    from hummingbot.model.range_position_collected_fees import RangePositionCollectedFees  # noqa: F401
    from hummingbot.model.trade_fill import TradeFill  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    HummingbotBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Provide a transactional session that rolls back after each test."""
    with Session(db_engine) as session:
        yield session
        session.rollback()


# ---------------------------------------------------------------------------
# FundingPayment
# ---------------------------------------------------------------------------


class TestFundingPaymentRepr:
    def _make_payment(self, db_session, **kwargs):
        from hummingbot.model.funding_payment import FundingPayment

        defaults = dict(
            timestamp=1_700_000_000_000,
            config_file_path="conf/strategy.yml",
            market="binance",
            rate=0.0001,
            symbol="BTC-USDT",
            amount=5.0,
        )
        defaults.update(kwargs)
        fp = FundingPayment(**defaults)
        db_session.add(fp)
        db_session.flush()
        return fp

    def test_repr_contains_key_fields(self, db_session):
        fp = self._make_payment(db_session)
        r = repr(fp)
        assert "FundingPayment" in r
        assert "binance" in r
        assert "BTC-USDT" in r

    def test_get_funding_payments_no_filters(self):
        from hummingbot.model.funding_payment import FundingPayment

        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        result = FundingPayment.get_funding_payments(session)
        assert result == []
        session.query.assert_called_once_with(FundingPayment)

    def test_get_funding_payments_with_all_filters(self):
        from hummingbot.model.funding_payment import FundingPayment

        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = ["payment1"]

        result = FundingPayment.get_funding_payments(
            session, timestamp="12345", market="binance", trading_pair="BTC-USDT"
        )
        assert result == ["payment1"]

    def test_to_pandas_with_payment(self, db_session):
        from hummingbot.model.funding_payment import FundingPayment

        fp = self._make_payment(db_session)
        df = FundingPayment.to_pandas([fp])
        assert len(df) == 1
        assert "Timestamp" in df.columns
        assert "Exchange" in df.columns
        assert "Amount" in df.columns
        assert df.index.name == "Index"

    def test_to_pandas_empty(self):
        from hummingbot.model.funding_payment import FundingPayment

        df = FundingPayment.to_pandas([])
        assert len(df) == 0


# ---------------------------------------------------------------------------
# MarketData
# ---------------------------------------------------------------------------


class TestMarketDataRepr:
    def test_repr_returns_string(self, db_session):
        from decimal import Decimal as D

        from hummingbot.model.market_data import MarketData

        md = MarketData(
            timestamp=D("1700000000.000000"),
            exchange="binance",
            trading_pair="BTC-USDT",
            mid_price=D("30000.000000"),
            best_bid=D("29999.000000"),
            best_ask=D("30001.000000"),
            order_book=None,
        )
        db_session.add(md)
        db_session.flush()
        # __repr__ inspects members for Column instances; calling it should not raise
        r = repr(md)
        assert isinstance(r, str)


# ---------------------------------------------------------------------------
# MarketState
# ---------------------------------------------------------------------------


class TestMarketStateRepr:
    def _make_state(self, db_session):
        from hummingbot.model.market_state import MarketState

        ms = MarketState(
            config_file_path="conf/strategy.yml",
            market="binance",
            timestamp=1_700_000_000_000,
            saved_state={"key": "val"},
        )
        db_session.add(ms)
        db_session.flush()
        return ms

    def test_repr_contains_fields(self, db_session):
        ms = self._make_state(db_session)
        r = repr(ms)
        assert "MarketState" in r
        assert "binance" in r
        assert "conf/strategy.yml" in r


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------


class TestOrderRepr:
    def _make_order(self, db_session, order_id="OID-001"):
        from hummingbot.model.order import Order

        o = Order(
            id=order_id,
            config_file_path="conf/strategy.yml",
            strategy="pure_market_making",
            market="binance",
            symbol="BTC-USDT",
            base_asset="BTC",
            quote_asset="USDT",
            creation_timestamp=1_700_000_000_000,
            order_type="LIMIT",
            amount=Decimal("0.1"),
            leverage=1,
            price=Decimal("30000"),
            last_status="OPEN",
            last_update_timestamp=1_700_000_001_000,
            exchange_order_id="EX-001",
            position=None,
        )
        db_session.add(o)
        db_session.flush()
        return o

    def test_repr_contains_fields(self, db_session):
        o = self._make_order(db_session)
        r = repr(o)
        assert "Order" in r
        assert "OID-001" in r
        assert "BTC-USDT" in r


# ---------------------------------------------------------------------------
# OrderStatus
# ---------------------------------------------------------------------------


class TestOrderStatusRepr:
    def _make_status(self, db_session):
        from hummingbot.model.order import Order
        from hummingbot.model.order_status import OrderStatus

        # Insert the parent Order first (FK reference)
        o = Order(
            id="OID-STATUS-001",
            config_file_path="conf/strategy.yml",
            strategy="pure_market_making",
            market="binance",
            symbol="BTC-USDT",
            base_asset="BTC",
            quote_asset="USDT",
            creation_timestamp=1_700_000_000_000,
            order_type="LIMIT",
            amount=Decimal("0.1"),
            leverage=1,
            price=Decimal("30000"),
            last_status="FILLED",
            last_update_timestamp=1_700_000_001_000,
        )
        db_session.add(o)
        db_session.flush()
        os_ = OrderStatus(
            order_id="OID-STATUS-001",
            timestamp=1_700_000_001_000,
            status="FILLED",
        )
        db_session.add(os_)
        db_session.flush()
        return os_

    def test_repr_contains_fields(self, db_session):
        os_ = self._make_status(db_session)
        r = repr(os_)
        assert "OrderStatus" in r
        assert "OID-STATUS-001" in r
        assert "FILLED" in r


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


class TestPositionRepr:
    def _make_position(self, db_session):
        from hummingbot.model.position import Position

        p = Position(
            id="POS-001",
            controller_id="ctrl-1",
            connector_name="binance",
            side="BUY",
            trading_pair="BTC-USDT",
            timestamp=1_700_000_000_000,
            volume_traded_quote=Decimal("300"),
            amount=Decimal("0.01"),
            breakeven_price=Decimal("30000"),
            unrealized_pnl_quote=Decimal("10"),
            realized_pnl_quote=Decimal("5"),
            cum_fees_quote=Decimal("1"),
        )
        db_session.add(p)
        db_session.flush()
        return p

    def test_repr_contains_fields(self, db_session):
        p = self._make_position(db_session)
        r = repr(p)
        assert "Position" in r
        assert "BTC-USDT" in r
        assert "binance" in r


# ---------------------------------------------------------------------------
# RangePositionCollectedFees
# ---------------------------------------------------------------------------


class TestRangePositionCollectedFeesRepr:
    def _make_rpcf(self, db_session):
        from hummingbot.model.range_position_collected_fees import RangePositionCollectedFees

        rpcf = RangePositionCollectedFees(
            config_file_path="conf/strategy.yml",
            strategy="amm_arb",
            token_id=123,
            token_0="WETH",
            token_1="USDC",
            claimed_fee_0=0.01,
            claimed_fee_1=5.0,
        )
        db_session.add(rpcf)
        db_session.flush()
        return rpcf

    def test_repr_contains_fields(self, db_session):
        rpcf = self._make_rpcf(db_session)
        r = repr(rpcf)
        assert "RangePositionCollectedFees" in r
        assert "WETH" in r
        assert "USDC" in r


# ---------------------------------------------------------------------------
# TradeFill
# ---------------------------------------------------------------------------


class TestTradeFillRepr:
    def _make_parent_order(self, db_session, order_id="TF-OID-001"):
        from hummingbot.model.order import Order

        o = Order(
            id=order_id,
            config_file_path="conf/strategy.yml",
            strategy="pure_market_making",
            market="binance",
            symbol="BTC-USDT",
            base_asset="BTC",
            quote_asset="USDT",
            creation_timestamp=1_699_999_990_000,
            order_type="LIMIT",
            amount=Decimal("0.1"),
            leverage=1,
            price=Decimal("30000"),
            last_status="FILLED",
            last_update_timestamp=1_700_000_000_000,
        )
        db_session.add(o)
        db_session.flush()
        return o

    def _make_trade_fill(self, db_session, parent_order=None, exchange_trade_id="EX-TRADE-001"):
        from hummingbot.model.trade_fill import TradeFill

        if parent_order is None:
            parent_order = self._make_parent_order(db_session, order_id=f"TF-OID-{exchange_trade_id}")
        tf = TradeFill(
            config_file_path="conf/strategy.yml",
            strategy="pure_market_making",
            market="binance",
            symbol="BTC-USDT",
            base_asset="BTC",
            quote_asset="USDT",
            timestamp=1_700_000_000_000,
            order_id=parent_order.id,
            trade_type="BUY",
            order_type="LIMIT",
            price=Decimal("30000"),
            amount=Decimal("0.1"),
            leverage=1,
            trade_fee={"percent": 0.001, "flat_fees": []},
            trade_fee_in_quote=Decimal("3"),
            exchange_trade_id=exchange_trade_id,
            position="NIL",
        )
        db_session.add(tf)
        db_session.flush()
        return tf

    def test_repr_contains_fields(self, db_session):
        tf = self._make_trade_fill(db_session)
        r = repr(tf)
        assert "TradeFill" in r
        assert "BTC-USDT" in r
        assert "EX-TRADE-001" in r

    def test_get_trades_no_filters(self):
        from hummingbot.model.trade_fill import TradeFill

        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        result = TradeFill.get_trades(session)
        assert result == []

    def test_get_trades_with_all_filters(self):
        from hummingbot.model.trade_fill import TradeFill

        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = ["trade1"]

        result = TradeFill.get_trades(
            session,
            strategy="pure_market_making",
            market="binance",
            trading_pair="BTC-USDT",
            base_asset="BTC",
            quote_asset="USDT",
            trade_type="BUY",
            order_type="LIMIT",
            start_time=1_000_000,
            end_time=2_000_000,
        )
        assert result == ["trade1"]

    def test_to_pandas_order_is_none(self):
        """Covers line 108: trade.order is None -> age = pd.Timestamp(0)."""
        import types

        from hummingbot.model.trade_fill import TradeFill

        tf = types.SimpleNamespace(
            config_file_path="conf/strategy.yml",
            strategy="pure_market_making",
            market="binance",
            symbol="BTC-USDT",
            base_asset="BTC",
            quote_asset="USDT",
            timestamp=1_700_000_000_000,
            order_id="OID-001",
            trade_type="BUY",
            order_type="LIMIT",
            price=Decimal("30000"),
            amount=Decimal("0.1"),
            leverage=1,
            trade_fee={"percent": 0.001, "flat_fees": []},
            trade_fee_in_quote=Decimal("3"),
            exchange_trade_id="EX-TRADE-NONE",
            position="NIL",
            order=None,
        )
        df = TradeFill.to_pandas([tf])
        assert len(df) == 1
        assert df.iloc[0]["Age"] == "00:00:00"

    def test_to_pandas_with_order(self):
        """Covers line 110-112: trade.order is not None -> age computed."""
        import types

        from hummingbot.model.trade_fill import TradeFill

        mock_order = MagicMock()
        mock_order.creation_timestamp = 1_699_999_990_000
        tf = types.SimpleNamespace(
            config_file_path="conf/strategy.yml",
            strategy="pure_market_making",
            market="binance",
            symbol="BTC-USDT",
            base_asset="BTC",
            quote_asset="USDT",
            timestamp=1_700_000_000_000,
            order_id="OID-001",
            trade_type="BUY",
            order_type="LIMIT",
            price=Decimal("30000"),
            amount=Decimal("0.1"),
            leverage=1,
            trade_fee={"percent": 0.001, "flat_fees": []},
            trade_fee_in_quote=Decimal("3"),
            exchange_trade_id="EX-TRADE-WITH-ORDER",
            position="NIL",
            order=mock_order,
        )
        df = TradeFill.to_pandas([tf])
        assert len(df) == 1
        assert "Age" in df.columns


# ---------------------------------------------------------------------------
# Migrator (db_migration)
# ---------------------------------------------------------------------------


class TestMigrator:
    def test_get_transformations_returns_list(self):
        from hummingbot.model.db_migration.migrator import Migrator

        transformations = Migrator._get_transformations()
        assert isinstance(transformations, list)

    def test_migrator_init_creates_transformation_instances(self):
        from hummingbot.model.db_migration.migrator import Migrator

        m = Migrator()
        assert hasattr(m, "transformations")
        assert isinstance(m.transformations, list)

    def test_migrate_db_calls_transformation_apply(self):
        """Covers lines 33-34, 43, 47, 52-54 of migrator.py."""
        from hummingbot.model.db_migration.base_transformation import DatabaseTransformation
        from hummingbot.model.db_migration.migrator import Migrator

        # Create a concrete transformation that reports it applies
        class ConcreteTransform(DatabaseTransformation):
            @property
            def name(self):
                return "test_transform"

            @property
            def to_version(self):
                return 2

            def apply(self, db_handle):
                return db_handle

        migrator = Migrator.__new__(Migrator)
        migrator.transformations = [ConcreteTransform(migrator)]

        client_config = MagicMock()
        db_handle = MagicMock()
        db_handle.db_path = "/tmp/test_hb_migrate.db"
        db_handle.engine = MagicMock()

        new_db_handle = MagicMock()
        new_db_handle.engine = MagicMock()

        with (
            patch("hummingbot.model.db_migration.migrator.copyfile"),
            patch("hummingbot.model.db_migration.migrator.move"),
            patch("hummingbot.model.db_migration.migrator.SQLConnectionManager", return_value=new_db_handle),
        ):
            result = migrator.migrate_db_to_version(client_config, db_handle, from_version=1, to_version=2)

        assert result is True


# ---------------------------------------------------------------------------
# DatabaseTransformation.add_column
# ---------------------------------------------------------------------------


class TestDatabaseTransformationAddColumn:
    def _make_concrete(self):
        from hummingbot.model.db_migration.base_transformation import DatabaseTransformation

        class ConcreteTransform(DatabaseTransformation):
            @property
            def name(self):
                return "concrete"

            @property
            def to_version(self):
                return 1

            def apply(self, db_handle):
                return db_handle

        migrator = MagicMock()
        return ConcreteTransform(migrator)

    def test_add_column_dry_run_true_logs_and_does_not_execute(self):
        """dry_run=True (default) logs the query, does NOT call engine.execute."""
        from sqlalchemy import Column, Text

        t = self._make_concrete()
        engine = MagicMock()
        engine.dialect = MagicMock()
        col = Column("new_col", Text, nullable=True)
        col_mock = MagicMock()
        col_mock.__str__ = lambda s: "new_col"

        with patch.object(col, "compile", return_value=col_mock):
            t.add_column(engine, "SomeTable", col, dry_run=True)

        engine.execute.assert_not_called()

    def test_add_column_dry_run_false_executes_query(self):
        """Covers line 56: engine.execute called when dry_run=False."""
        from sqlalchemy import Column, Text

        t = self._make_concrete()
        engine = MagicMock()
        engine.dialect = MagicMock()
        col = Column("new_col", Text, nullable=True)
        col_mock = MagicMock()
        col_mock.__str__ = lambda s: "new_col"

        with patch.object(col, "compile", return_value=col_mock):
            t.add_column(engine, "SomeTable", col, dry_run=False)

        engine.execute.assert_called_once()
