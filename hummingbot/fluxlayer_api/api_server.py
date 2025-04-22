import uvicorn
from fastapi import FastAPI, Depends
from pydantic import BaseModel, Field
import sys
import os
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.append(project_root)

from hummingbot.fluxlayer_api.rfq import get_single_exchange_rfq, get_best_rfq

app_host="0.0.0.0"
app_port=8080

class GetRFQRequest(BaseModel):
    src_chain: str = Field(..., description="源链, cobo wallet 格式")
    src_token: str = Field(..., description="源token, cobo wallet 格式")
    src_amount: float = Field(..., description="交易数量")
    tar_chain: str = Field(..., description="目标链, cobo wallet 格式")
    tar_token: str = Field(..., description="目标token, cobo wallet 格式")
    exchange_name: str = Field(..., description="交易所名")

class GetBestRFQRequest(BaseModel):
    src_chain: str = Field(..., description="源链, cobo wallet 格式")
    src_token: str = Field(..., description="源token, cobo wallet 格式")
    src_amount: float = Field(..., description="交易数量")
    tar_chain: str = Field(..., description="目标链, cobo wallet 格式")
    tar_token: str = Field(..., description="目标token, cobo wallet 格式")

server = FastAPI()

@server.post("/rfq_request")
async def get_rfq_request(req: GetRFQRequest):
    data = await get_single_exchange_rfq(req.src_chain, req.src_token, req.src_amount, req.tar_chain, req.tar_token, req.exchange_name)
    return data

@server.post("/get_best_rfq")
async def get_best_rfq_request(req: GetBestRFQRequest):
    data = await get_best_rfq(req.src_chain, req.src_token, req.src_amount, req.tar_chain, req.tar_token)
    return data

if __name__ == "__main__":
    uvicorn.run(server, host=app_host, port=app_port)
