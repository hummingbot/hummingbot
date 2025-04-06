import time
from typing import Any, Tuple

import sha3
from coincurve import PrivateKey
from eip712_structs import make_domain
from eth_utils import big_endian_to_int

import hummingbot.connector.exchange.vertex.vertex_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


def keccak_hash(x):
    return sha3.keccak_256(x).digest()


class VertexAuth(AuthBase):
    def __init__(self, vertex_arbitrum_address: str, vertex_arbitrum_private_key: str):
        self.sender_address = vertex_arbitrum_address
        self.private_key = vertex_arbitrum_private_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        This method is intended to configure a rest request to be authenticated. Vertex does not use this
        functionality.

        :param request: the request to be configured for authenticated interaction
        """
        return request  # pass-through

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Vertex does not use this
        functionality.

        :param request: the request to be configured for authenticated interaction
        """
        return request  # pass-through

    def get_referral_code_headers(self):
        """
        Generates referral headers when supported by Vertex

        :return: a dictionary of auth headers
        """
        headers = {"referer": CONSTANTS.HBOT_BROKER_ID}
        return headers

    def sign_payload(self, payload: Any, contract: str, chain_id: int) -> Tuple[str, str]:
        """
        Signs the payload using the sender address (address with subaccount identifier) and private key
        provided in the configuration.

        :param payload: the payload using EIP712 structure for signature (eg. order, cancel)
        :param contract: the market or general contract signing in domain struct creation for Vertex
        :param chain_id: the chain used for domain struct creation (NOTE: different for testnet vs mainnet)

        :return: a tuple for both a string hex of the signature of the EIP712 payload and a string hex of
        the digest
        """
        domain = make_domain(name="Vertex", version=CONSTANTS.VERSION, chainId=chain_id, verifyingContract=contract)

        signable_bytes = payload.signable_bytes(domain)
        # Digest for order tracking in Hummingbot
        digest = self.generate_digest(signable_bytes)

        pk = PrivateKey.from_hex(self.private_key)
        signature = pk.sign_recoverable(signable_bytes, hasher=keccak_hash)

        v = signature[64] + 27
        r = big_endian_to_int(signature[0:32])
        s = big_endian_to_int(signature[32:64])

        final_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big") + v.to_bytes(1, "big")
        return f"0x{final_sig.hex()}", digest

    def generate_digest(self, signable_bytes: bytearray) -> str:
        """
        Generates the digest of the payload for use across Vetext lookups

        :param signable_bytes: the bytes of the payload

        :return: a string hex of the keccak_256 of the signable_bytes of the payload
        """
        return f"0x{keccak_hash(signable_bytes).hex()}"

    def _time(self):
        return time.time()
