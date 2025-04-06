from pyinjective.proto.cosmos.auth.v1beta1 import query_pb2 as auth_query_pb


class AuthParams:
    def __init__(
        self,
        max_memo_characters: int,
        tx_sig_limit: int,
        tx_size_cost_per_byte: int,
        sig_verify_cost_ed25519: int,
        sig_verify_cost_secp256k1: int,
    ):
        super().__init__()
        self.max_memo_characters = max_memo_characters
        self.tx_sig_limit = tx_sig_limit
        self.tx_size_cost_per_byte = tx_size_cost_per_byte
        self.sig_verify_cost_ed25519 = sig_verify_cost_ed25519
        self.sig_verify_cost_secp256k1 = sig_verify_cost_secp256k1

    @classmethod
    def from_proto_response(cls, response: auth_query_pb.QueryParamsResponse):
        return cls(
            max_memo_characters=response.params.max_memo_characters,
            tx_sig_limit=response.params.tx_sig_limit,
            tx_size_cost_per_byte=response.params.tx_size_cost_per_byte,
            sig_verify_cost_ed25519=response.params.sig_verify_cost_ed25519,
            sig_verify_cost_secp256k1=response.params.sig_verify_cost_secp256k1,
        )
