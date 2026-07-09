import json

import base58
import pytest
from solders.keypair import Keypair

# Import the module under test
from hummingbot.connector.derivative.pacifica_perpetual import pacifica_perpetual_auth as auth_mod
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


def generate_dummy_keypair():
    # Generate a random keypair using the library's constructor
    return Keypair()


DUMMY_KEYPAIR = generate_dummy_keypair()


class DummyRESTRequest:
    def __init__(self, method, data=None, headers=None, url=""):
        self.method = method
        self.data = data
        self.headers = headers if headers is not None else {}
        self.url = url


class DummyWSRequest:
    def __init__(self, payload):
        self.payload = payload


def test_prepare_message_success_and_compact():
    header = {"type": "order", "timestamp": 123456789, "expiry_window": 5000}
    payload = {"price": 100, "amount": 1}
    msg = auth_mod.prepare_message(header, payload)
    # Ensure it's a compact JSON string (no spaces after commas/colons)
    assert "," in msg and ":" in msg
    # Load back to dict and verify structure
    loaded = json.loads(msg)
    assert loaded["type"] == "order"
    assert loaded["timestamp"] == 123456789
    assert loaded["expiry_window"] == 5000
    assert loaded["data"] == payload
    # Ensure keys are sorted alphabetically at top level
    top_keys = list(loaded.keys())
    assert top_keys == sorted(top_keys)


def test_prepare_message_missing_fields_raises():
    # Missing 'type'
    header_missing = {"timestamp": 1, "expiry_window": 2}
    payload = {}
    with pytest.raises(ValueError):
        auth_mod.prepare_message(header_missing, payload)
    # Missing 'timestamp'
    header_missing = {"type": "x", "expiry_window": 2}
    with pytest.raises(ValueError):
        auth_mod.prepare_message(header_missing, payload)
    # Missing 'expiry_window'
    header_missing = {"type": "x", "timestamp": 1}
    with pytest.raises(ValueError):
        auth_mod.prepare_message(header_missing, payload)


def test_sort_json_keys_preserves_structure_and_order():
    unsorted = {"b": 2, "a": {"d": 4, "c": 3}}
    sorted_result = auth_mod.sort_json_keys(unsorted)
    # Top-level keys should be sorted
    assert list(sorted_result.keys()) == ["a", "b"]
    # Nested dict keys should also be sorted
    assert list(sorted_result["a"].keys()) == ["c", "d"]


@pytest.mark.asyncio
async def test_rest_authenticate_adds_fields_and_signature(monkeypatch):
    # Prepare request with POST method and minimal data
    data = {"type": "order", "price": 100}
    request = DummyRESTRequest(method=RESTMethod.POST, data=json.dumps(data))
    # Patch the sign_message function to return a predictable signature

    def fake_sign_message(header, payload, keypair):
        return ("msg", "FAKESIG")
    monkeypatch.setattr(auth_mod, "sign_message", fake_sign_message)
    # Use a valid secret key from our DUMMY_KEYPAIR (full 64 bytes)
    valid_secret = base58.b58encode(bytes(DUMMY_KEYPAIR)).decode("ascii")
    auth = auth_mod.PacificaPerpetualAuth(agent_wallet_public_key="pub", agent_wallet_private_key=valid_secret, user_wallet_public_key="user")

    # Run authentication
    await auth.rest_authenticate(request)
    # Verify request data now includes additional fields
    result_data = json.loads(request.data)
    for field in ["account", "agent_wallet", "signature", "timestamp", "expiry_window"]:
        assert field in result_data
    assert result_data["account"] == "user"
    assert result_data["agent_wallet"] == "pub"
    assert result_data["signature"] == "FAKESIG"
    # Original fields should still be present
    assert result_data["price"] == 100


@pytest.mark.asyncio
async def test_ws_authenticate_mutates_payload(monkeypatch):
    payload = {"type": "subscribe", "channel": "book"}
    request = DummyWSRequest(payload={"params": payload.copy()})
    # Patch sign_message similarly

    def fake_sign_message(header, payload, keypair):
        return ("msg", "WSIG")
    monkeypatch.setattr(auth_mod, "sign_message", fake_sign_message)

    valid_secret = base58.b58encode(bytes(DUMMY_KEYPAIR)).decode("ascii")
    auth = auth_mod.PacificaPerpetualAuth(agent_wallet_public_key="pub", agent_wallet_private_key=valid_secret, user_wallet_public_key="user")

    # Run authentication
    # Run authentication
    await auth.ws_authenticate(request)
    final_params = request.payload["params"]
    for field in ["account", "agent_wallet", "signature", "timestamp", "expiry_window"]:
        assert field in final_params
    assert final_params["account"] == "pub"
    assert final_params["agent_wallet"] == "pub"
    assert final_params["signature"] == "WSIG"
    # Original fields retained
    assert final_params["channel"] == "book"
