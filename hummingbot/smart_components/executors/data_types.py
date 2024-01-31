from pydantic import BaseModel


class ExecutorConfigBase(BaseModel):
    id: str
    timestamp: float
