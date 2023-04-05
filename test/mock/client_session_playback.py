from test.mock.client_session_request_utils import (
    Base,
    ClientSessionRequestMethod,
    ClientSessionRequestType,
    ClientSessionResponseType,
)
from typing import Any, Dict

from sqlalchemy import JSON, BigInteger, Column, Enum as SQLEnum, Integer, Text


class ClientSessionPlayback(Base):
    __tablename__ = "ClientSessionPlayback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, nullable=False)
    url = Column(Text, index=True, nullable=False)
    method = Column(SQLEnum(ClientSessionRequestMethod), nullable=False)
    request_type = Column(SQLEnum(ClientSessionRequestType), nullable=False)
    request_params = Column(JSON)
    request_json = Column(JSON)
    response_type = Column(SQLEnum(ClientSessionResponseType), nullable=False)
    response_code = Column(Integer, nullable=False)
    response_text = Column(Text)
    response_json = Column(JSON)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "url": self.url,
            "method": self.method,
            "request_type": self.request_type,
            "request_params": self.request_params,
            "request_json": self.request_json,
            "response_type": self.response_type,
            "response_code": self.response_code,
            "response_text": self.response_text,
            "response_json": self.response_json,
        }
