import uvicorn
from fastapi import FastAPI, Depends
from pydantic import BaseModel, Field
import sys
import os
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.append(project_root)

from hummingbot.fluxlayer_api.rfq import rfq_demo

app_host="0.0.0.0"
app_port=8080

class GetRFQRequest(BaseModel):
    trading_pair: str = Field(..., description="代币对")
    SrcAmount: int = Field(..., description="传入数量")

server = FastAPI()

@server.post("/rfq_request")
async def get_rfq_request(req: GetRFQRequest):
    data = await rfq_demo(req.trading_pair, req.SrcAmount)
    print(data)
    return data

if __name__ == "__main__":
    uvicorn.run(server, host=app_host, port=app_port)
