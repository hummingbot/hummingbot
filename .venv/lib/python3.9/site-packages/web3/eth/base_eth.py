from typing import (
    Any,
    List,
    NoReturn,
    Optional,
    Tuple,
    Union,
)

from eth_account import (
    Account,
)
from eth_typing import (
    Address,
    ChecksumAddress,
    HexStr,
)
from eth_utils import (
    is_checksum_address,
    is_string,
)
from eth_utils.toolz import (
    assoc,
)

from web3._utils.empty import (
    Empty,
    empty,
)
from web3._utils.encoding import (
    to_hex,
)
from web3.exceptions import (
    Web3TypeError,
    Web3ValueError,
)
from web3.module import (
    Module,
)
from web3.types import (
    ENS,
    BlockIdentifier,
    FilterParams,
    GasPriceStrategy,
    StateOverride,
    TxParams,
    Wei,
)


class BaseEth(Module):
    _default_account: Union[ChecksumAddress, Empty] = empty
    _default_block: BlockIdentifier = "latest"
    _default_contract_factory: Any = None
    _gas_price_strategy = None

    is_async = False
    account = Account()

    def namereg(self) -> NoReturn:
        raise NotImplementedError()

    def icap_namereg(self) -> NoReturn:
        raise NotImplementedError()

    @property
    def default_block(self) -> BlockIdentifier:
        return self._default_block

    @default_block.setter
    def default_block(self, value: BlockIdentifier) -> None:
        self._default_block = value

    @property
    def default_account(self) -> Union[ChecksumAddress, Empty]:
        return self._default_account

    @default_account.setter
    def default_account(self, account: Union[ChecksumAddress, Empty]) -> None:
        self._default_account = account

    def send_transaction_munger(self, transaction: TxParams) -> Tuple[TxParams]:
        if "from" not in transaction and is_checksum_address(self.default_account):
            transaction = assoc(transaction, "from", self.default_account)

        return (transaction,)

    def generate_gas_price(
        self, transaction_params: Optional[TxParams] = None
    ) -> Optional[Wei]:
        if self._gas_price_strategy:
            return self._gas_price_strategy(self.w3, transaction_params)
        return None

    def set_gas_price_strategy(
        self, gas_price_strategy: Optional[GasPriceStrategy]
    ) -> None:
        self._gas_price_strategy = gas_price_strategy

    def _eth_call_and_estimate_gas_munger(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
    ) -> Union[
        Tuple[TxParams, BlockIdentifier],
        Tuple[TxParams, BlockIdentifier, StateOverride],
    ]:
        # TODO: move to middleware
        if "from" not in transaction and is_checksum_address(self.default_account):
            transaction = assoc(transaction, "from", self.default_account)

        # TODO: move to middleware
        if block_identifier is None:
            block_identifier = self.default_block

        if state_override is None:
            return (transaction, block_identifier)
        else:
            return (transaction, block_identifier, state_override)

    def estimate_gas_munger(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
    ) -> Union[
        Tuple[TxParams, BlockIdentifier],
        Tuple[TxParams, BlockIdentifier, StateOverride],
    ]:
        return self._eth_call_and_estimate_gas_munger(
            transaction, block_identifier, state_override
        )

    def get_block_munger(
        self, block_identifier: BlockIdentifier, full_transactions: bool = False
    ) -> Tuple[BlockIdentifier, bool]:
        return (block_identifier, full_transactions)

    def block_id_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> Tuple[Union[Address, ChecksumAddress, ENS], BlockIdentifier]:
        if block_identifier is None:
            block_identifier = self.default_block
        return (account, block_identifier)

    def get_storage_at_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        position: int,
        block_identifier: Optional[BlockIdentifier] = None,
    ) -> Tuple[Union[Address, ChecksumAddress, ENS], int, BlockIdentifier]:
        if block_identifier is None:
            block_identifier = self.default_block
        return (account, position, block_identifier)

    def call_munger(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[StateOverride] = None,
    ) -> Union[
        Tuple[TxParams, BlockIdentifier],
        Tuple[TxParams, BlockIdentifier, StateOverride],
    ]:
        return self._eth_call_and_estimate_gas_munger(
            transaction, block_identifier, state_override
        )

    def create_access_list_munger(
        self, transaction: TxParams, block_identifier: Optional[BlockIdentifier] = None
    ) -> Tuple[TxParams, BlockIdentifier]:
        # TODO: move to middleware
        if "from" not in transaction and is_checksum_address(self.default_account):
            transaction = assoc(transaction, "from", self.default_account)

        # TODO: move to middleware
        if block_identifier is None:
            block_identifier = self.default_block

        return (transaction, block_identifier)

    def sign_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        data: Union[int, bytes] = None,
        hexstr: HexStr = None,
        text: str = None,
    ) -> Tuple[Union[Address, ChecksumAddress, ENS], HexStr]:
        message_hex = to_hex(data, hexstr=hexstr, text=text)
        return (account, message_hex)

    def filter_munger(
        self,
        filter_params: Optional[Union[str, FilterParams]] = None,
        filter_id: Optional[HexStr] = None,
    ) -> Union[List[FilterParams], List[HexStr], List[str]]:
        if filter_id and filter_params:
            raise Web3TypeError(
                "Ambiguous invocation: provide either a `filter_params` or a "
                "`filter_id` argument. Both were supplied."
            )
        if isinstance(filter_params, dict):
            return [filter_params]
        elif is_string(filter_params):
            if filter_params in {"latest", "pending"}:
                return [filter_params]
            else:
                raise Web3ValueError(
                    "The filter API only accepts the values of `pending` or "
                    "`latest` for string based filters"
                )
        elif filter_id and not filter_params:
            return [filter_id]
        else:
            raise Web3TypeError(
                "Must provide either filter_params as a string or "
                "a valid filter object, or a filter_id as a string "
                "or hex."
            )
