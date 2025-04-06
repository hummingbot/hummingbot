from typing import (
    Optional,
)

from web3._utils.rpc_abi import (
    RPC,
)
from web3.module import (
    Module,
)


class Testing(Module):
    def timeTravel(self, timestamp: int) -> None:
        self.w3.manager.request_blocking(RPC.testing_timeTravel, [timestamp])

    def mine(self, num_blocks: int = 1) -> None:
        self.w3.manager.request_blocking(RPC.evm_mine, [num_blocks])

    def snapshot(self) -> int:
        self.last_snapshot_idx = self.w3.manager.request_blocking(RPC.evm_snapshot, [])
        return self.last_snapshot_idx

    def reset(self) -> None:
        self.w3.manager.request_blocking(RPC.evm_reset, [])

    def revert(self, snapshot_idx: Optional[int] = None) -> None:
        if snapshot_idx is None:
            revert_target = self.last_snapshot_idx
        else:
            revert_target = snapshot_idx
        self.w3.manager.request_blocking(RPC.evm_revert, [revert_target])
