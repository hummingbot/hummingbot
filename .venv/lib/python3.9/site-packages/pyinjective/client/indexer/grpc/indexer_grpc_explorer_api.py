from typing import Any, Callable, Dict, List, Optional

from grpc.aio import Channel

from pyinjective.client.model.pagination import PaginationOption
from pyinjective.core.network import CookieAssistant
from pyinjective.proto.exchange import (
    injective_explorer_rpc_pb2 as exchange_explorer_pb,
    injective_explorer_rpc_pb2_grpc as exchange_explorer_grpc,
)
from pyinjective.utils.grpc_api_request_assistant import GrpcApiRequestAssistant


class IndexerGrpcExplorerApi:
    def __init__(self, channel: Channel, cookie_assistant: CookieAssistant):
        self._stub = self._stub = exchange_explorer_grpc.InjectiveExplorerRPCStub(channel)
        self._assistant = GrpcApiRequestAssistant(cookie_assistant=cookie_assistant)

    async def fetch_account_txs(
        self,
        address: str,
        before: Optional[int] = None,
        after: Optional[int] = None,
        message_type: Optional[str] = None,
        module: Optional[str] = None,
        from_number: Optional[int] = None,
        to_number: Optional[int] = None,
        status: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetAccountTxsRequest(
            address=address,
            before=before,
            after=after,
            limit=pagination.limit,
            skip=pagination.skip,
            type=message_type,
            module=module,
            from_number=from_number,
            to_number=to_number,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            status=status,
        )

        response = await self._execute_call(call=self._stub.GetAccountTxs, request=request)

        return response

    async def fetch_contract_txs(
        self,
        address: str,
        from_number: Optional[int] = None,
        to_number: Optional[int] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetAccountTxsRequest(
            address=address,
            limit=pagination.limit,
            skip=pagination.skip,
            from_number=from_number,
            to_number=to_number,
        )

        response = await self._execute_call(call=self._stub.GetContractTxs, request=request)

        return response

    async def fetch_contract_txs_v2(
        self,
        address: str,
        height: Optional[int] = None,
        token: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetContractTxsV2Request(
            address=address,
            token=token,
        )
        if height is not None:
            request.height = height
        if pagination is not None:
            setattr(request, "from", pagination.start_time)
            request.to = pagination.end_time
            request.limit = pagination.limit

        response = await self._execute_call(call=self._stub.GetContractTxsV2, request=request)

        return response

    async def fetch_blocks(
        self,
        before: Optional[int] = None,
        after: Optional[int] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetBlocksRequest(
            before=before,
            after=after,
            limit=pagination.limit,
        )

        response = await self._execute_call(call=self._stub.GetBlocks, request=request)

        return response

    async def fetch_block(self, block_id: str) -> Dict[str, Any]:
        request = exchange_explorer_pb.GetBlockRequest(id=block_id)

        response = await self._execute_call(call=self._stub.GetBlock, request=request)

        return response

    async def fetch_validators(self) -> Dict[str, Any]:
        request = exchange_explorer_pb.GetValidatorsRequest()

        response = await self._execute_call(call=self._stub.GetValidators, request=request)

        return response

    async def fetch_validator(self, address: str) -> Dict[str, Any]:
        request = exchange_explorer_pb.GetValidatorRequest(address=address)

        response = await self._execute_call(call=self._stub.GetValidator, request=request)

        return response

    async def fetch_validator_uptime(self, address: str) -> Dict[str, Any]:
        request = exchange_explorer_pb.GetValidatorUptimeRequest(address=address)

        response = await self._execute_call(call=self._stub.GetValidatorUptime, request=request)

        return response

    async def fetch_txs(
        self,
        before: Optional[int] = None,
        after: Optional[int] = None,
        message_type: Optional[str] = None,
        module: Optional[str] = None,
        from_number: Optional[int] = None,
        to_number: Optional[int] = None,
        status: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetTxsRequest(
            before=before,
            after=after,
            limit=pagination.limit,
            skip=pagination.skip,
            type=message_type,
            module=module,
            from_number=from_number,
            to_number=to_number,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            status=status,
        )

        response = await self._execute_call(call=self._stub.GetTxs, request=request)

        return response

    async def fetch_tx_by_tx_hash(self, tx_hash: str) -> Dict[str, Any]:
        request = exchange_explorer_pb.GetTxByTxHashRequest(hash=tx_hash)

        response = await self._execute_call(call=self._stub.GetTxByTxHash, request=request)

        return response

    async def fetch_peggy_deposit_txs(
        self,
        sender: Optional[str] = None,
        receiver: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetPeggyDepositTxsRequest(
            sender=sender,
            receiver=receiver,
            limit=pagination.limit,
            skip=pagination.skip,
        )

        response = await self._execute_call(call=self._stub.GetPeggyDepositTxs, request=request)

        return response

    async def fetch_peggy_withdrawal_txs(
        self,
        sender: Optional[str] = None,
        receiver: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetPeggyWithdrawalTxsRequest(
            sender=sender,
            receiver=receiver,
            limit=pagination.limit,
            skip=pagination.skip,
        )

        response = await self._execute_call(call=self._stub.GetPeggyWithdrawalTxs, request=request)

        return response

    async def fetch_ibc_transfer_txs(
        self,
        sender: Optional[str] = None,
        receiver: Optional[str] = None,
        src_channel: Optional[str] = None,
        src_port: Optional[str] = None,
        dest_channel: Optional[str] = None,
        dest_port: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetIBCTransferTxsRequest(
            sender=sender,
            receiver=receiver,
            src_channel=src_channel,
            src_port=src_port,
            dest_channel=dest_channel,
            dest_port=dest_port,
            limit=pagination.limit,
            skip=pagination.skip,
        )

        response = await self._execute_call(call=self._stub.GetIBCTransferTxs, request=request)

        return response

    async def fetch_wasm_codes(
        self,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetWasmCodesRequest(
            limit=pagination.limit,
            from_number=pagination.from_number,
            to_number=pagination.to_number,
        )

        response = await self._execute_call(call=self._stub.GetWasmCodes, request=request)

        return response

    async def fetch_wasm_code_by_id(
        self,
        code_id: int,
    ) -> Dict[str, Any]:
        request = exchange_explorer_pb.GetWasmCodeByIDRequest(code_id=code_id)

        response = await self._execute_call(call=self._stub.GetWasmCodeByID, request=request)

        return response

    async def fetch_wasm_contracts(
        self,
        code_id: Optional[int] = None,
        assets_only: Optional[bool] = None,
        label: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetWasmContractsRequest(
            limit=pagination.limit,
            code_id=code_id,
            from_number=pagination.from_number,
            to_number=pagination.to_number,
            assets_only=assets_only,
            skip=pagination.skip,
            label=label,
        )

        response = await self._execute_call(call=self._stub.GetWasmContracts, request=request)

        return response

    async def fetch_wasm_contract_by_address(
        self,
        address: str,
    ) -> Dict[str, Any]:
        request = exchange_explorer_pb.GetWasmContractByAddressRequest(contract_address=address)

        response = await self._execute_call(call=self._stub.GetWasmContractByAddress, request=request)

        return response

    async def fetch_cw20_balance(
        self,
        address: str,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetCw20BalanceRequest(
            address=address,
            limit=pagination.limit,
        )

        response = await self._execute_call(call=self._stub.GetCw20Balance, request=request)

        return response

    async def fetch_relayers(
        self,
        market_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        request = exchange_explorer_pb.RelayersRequest(market_i_ds=market_ids)

        response = await self._execute_call(call=self._stub.Relayers, request=request)

        return response

    async def fetch_bank_transfers(
        self,
        senders: Optional[List[str]] = None,
        recipients: Optional[List[str]] = None,
        is_community_pool_related: Optional[bool] = None,
        address: Optional[List[str]] = None,
        per_page: Optional[int] = None,
        token: Optional[str] = None,
        pagination: Optional[PaginationOption] = None,
    ) -> Dict[str, Any]:
        pagination = pagination or PaginationOption()
        request = exchange_explorer_pb.GetBankTransfersRequest(
            senders=senders,
            recipients=recipients,
            is_community_pool_related=is_community_pool_related,
            limit=pagination.limit,
            skip=pagination.skip,
            start_time=pagination.start_time,
            end_time=pagination.end_time,
            address=address,
            per_page=per_page,
            token=token,
        )

        response = await self._execute_call(call=self._stub.GetBankTransfers, request=request)

        return response

    async def _execute_call(self, call: Callable, request) -> Dict[str, Any]:
        return await self._assistant.execute_call(call=call, request=request)
