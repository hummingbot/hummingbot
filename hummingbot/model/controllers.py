from sqlalchemy import JSON, Column, Float, Index, Text

from hummingbot.model import HummingbotBase


class Controllers(HummingbotBase):
    __tablename__ = "Controllers"
    __table_args__ = (
        Index("c_type", "type"),
    )
    id = Column(Text, primary_key=True)
    timestamp = Column(Float, nullable=False)
    type = Column(Text, nullable=False)
    config = Column(JSON, nullable=False)
