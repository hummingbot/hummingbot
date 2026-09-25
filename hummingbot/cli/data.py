"""Read-only access to a bot's trades sqlite DB, independent of any running process."""
import time
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload, sessionmaker

from hummingbot.model import get_declarative_base
from hummingbot.model.trade_fill import TradeFill


def get_trades(db_path: str,
               *,
               config_file_path: Optional[str] = None,
               days: Optional[float] = None,
               limit: Optional[int] = None) -> List[TradeFill]:
    """Return TradeFill rows (ascending by timestamp), detached from the session."""
    get_declarative_base()  # register every model so the TradeFill -> Order mapper resolves
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        # Eager-load the related Order so consumers (e.g. TradeFill.to_pandas, which reads
        # order.creation_timestamp) work after the rows are detached from the session.
        query = session.query(TradeFill).options(joinedload(TradeFill.order))
        if config_file_path:
            query = query.filter(TradeFill.config_file_path.like(f"%{config_file_path}%"))
        if days:
            start_ms = int((time.time() - days * 86400) * 1e3)
            query = query.filter(TradeFill.timestamp >= start_ms)
        query = query.order_by(TradeFill.timestamp.desc())
        if limit:
            query = query.limit(limit)
        trades = query.all()
        session.expunge_all()
        return list(reversed(trades))
    finally:
        session.close()
        engine.dispose()
