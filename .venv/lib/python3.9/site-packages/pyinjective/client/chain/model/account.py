from google.protobuf import any_pb2

from pyinjective.proto.injective.types.v1beta1 import account_pb2 as account_pb


class Account:
    def __init__(
        self,
        address: str,
        pub_key_type_url: str,
        pub_key_value: bytes,
        account_number: int,
        sequence: int,
        code_hash: str,
    ):
        super().__init__()
        self.address = address
        self.pub_key_type_url = pub_key_type_url
        self.pub_key_value = pub_key_value
        self.account_number = account_number
        self.sequence = sequence
        self.code_hash = code_hash

    @classmethod
    def from_proto(cls, proto_account: any_pb2.Any):
        eth_account = account_pb.EthAccount()
        proto_account.Unpack(eth_account)
        pub_key_type_url = None
        pub_key_value = None

        if eth_account.base_account.pub_key is not None:
            pub_key_type_url = eth_account.base_account.pub_key.type_url
            pub_key_value = eth_account.base_account.pub_key.value

        return cls(
            address=eth_account.base_account.address,
            pub_key_type_url=pub_key_type_url,
            pub_key_value=pub_key_value,
            account_number=eth_account.base_account.account_number,
            sequence=eth_account.base_account.sequence,
            code_hash=f"0x{eth_account.code_hash.hex()}",
        )
