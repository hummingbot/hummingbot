from eip712_structs import Address, Array, Bytes, EIP712Struct, Int, String, Uint


class EIP712Domain(EIP712Struct):
    name = String()
    version = String()
    chainId = Uint(256)
    verifyingContract = Address()


# https://vertex-protocol.gitbook.io/docs/developer-resources/api/websocket-rest-api/executes/place-order
class Order(EIP712Struct):
    sender = Bytes(32)
    priceX18 = Int(128)
    amount = Int(128)
    expiration = Uint(64)
    nonce = Uint(64)


# https://vertex-protocol.gitbook.io/docs/developer-resources/api/websocket-rest-api/executes/cancel-orders
class Cancellation(EIP712Struct):
    sender = Bytes(32)
    productIds = Array(Uint(32))
    digests = Array(Bytes(32))
    nonce = Uint(64)


# https://vertex-protocol.gitbook.io/docs/developer-resources/api/websocket-rest-api/executes/cancel-product-orders
class CancellationProducts(EIP712Struct):
    sender = Bytes(32)
    productIds = Array(Uint(32))
    nonce = Uint(64)
