"""
Coverage tests for ConfigEncoderDecoder: enum decode path, yaml_dump, yaml_load.
Targets lines 27, 46, 50 of config_encoder_decoder.py.
"""

from decimal import Decimal
from enum import Enum

from hummingbot.strategy_v2.utils.config_encoder_decoder import ConfigEncoderDecoder


class Color(Enum):
    RED = 1
    BLUE = 2


class TestConfigEncoderDecoderEnumDecode:
    def setup_method(self):
        self.encoder = ConfigEncoderDecoder(Color)

    def test_decode_enum_path_known_class(self):
        """Covers line 27-29: __enum__ dict with a registered class returns enum member."""
        encoded = {"__enum__": True, "class": "Color", "value": "RED"}
        result = self.encoder.recursive_decode(encoded)
        assert result is Color.RED

    def test_decode_enum_path_unknown_class_returns_none(self):
        """Covers line 27 branch: __enum__ True but class not in registry -> returns None."""
        encoded = {"__enum__": True, "class": "UnknownClass", "value": "FOO"}
        # enum_class will be None, so the if branch is skipped, no else -> returns None
        result = self.encoder.recursive_decode(encoded)
        assert result is None

    def test_encode_then_decode_enum_roundtrip(self):
        """Full roundtrip: encode enum -> JSON string -> decode back to enum."""
        data = {"color": Color.BLUE, "value": Decimal("3.14")}
        encoded_str = self.encoder.encode(data)
        decoded = self.encoder.decode(encoded_str)
        assert decoded["color"] is Color.BLUE
        assert decoded["value"] == Decimal("3.14")

    def test_decode_nested_list_with_enum(self):
        encoded = [{"__enum__": True, "class": "Color", "value": "BLUE"}]
        result = self.encoder.recursive_decode(encoded)
        assert result == [Color.BLUE]


class TestConfigEncoderDecoderYaml:
    def setup_method(self):
        self.encoder = ConfigEncoderDecoder(Color)

    def test_yaml_dump_writes_file(self, tmp_path):
        """Covers line 46: yaml_dump opens file and writes encoded data."""
        file_path = tmp_path / "config.yaml"
        data = {"color": Color.RED, "amount": Decimal("1.5"), "name": "test"}
        self.encoder.yaml_dump(data, str(file_path))
        assert file_path.exists()
        content = file_path.read_text()
        assert "color" in content

    def test_yaml_load_reads_file(self, tmp_path):
        """Covers line 50: yaml_load opens file and returns decoded data."""
        file_path = tmp_path / "config.yaml"
        data = {"color": Color.RED, "name": "test"}
        self.encoder.yaml_dump(data, str(file_path))
        loaded = self.encoder.yaml_load(str(file_path))
        assert loaded["color"] is Color.RED
        assert loaded["name"] == "test"

    def test_yaml_roundtrip_with_decimal(self, tmp_path):
        """yaml_dump then yaml_load preserves Decimal values."""
        file_path = tmp_path / "config_decimal.yaml"
        data = {"price": Decimal("99.99"), "label": "item"}
        self.encoder.yaml_dump(data, str(file_path))
        loaded = self.encoder.yaml_load(str(file_path))
        assert loaded["price"] == Decimal("99.99")
