# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: penumbra/core/asset/v1alpha1/asset.proto
"""Generated protocol buffer code."""
from google.protobuf import (
    descriptor as _descriptor,
    descriptor_pool as _descriptor_pool,
    symbol_database as _symbol_database,
)
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.num.v1alpha1 import (
    num_pb2 as penumbra_dot_core_dot_num_dot_v1alpha1_dot_num__pb2,
)

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n(penumbra/core/asset/v1alpha1/asset.proto\x12\x1cpenumbra.core.asset.v1alpha1\x1a$penumbra/core/num/v1alpha1/num.proto\"\"\n\x11\x42\x61lanceCommitment\x12\r\n\x05inner\x18\x01 \x01(\x0c\"E\n\x07\x41ssetId\x12\r\n\x05inner\x18\x01 \x01(\x0c\x12\x13\n\x0b\x61lt_bech32m\x18\x02 \x01(\t\x12\x16\n\x0e\x61lt_base_denom\x18\x03 \x01(\t\"\x16\n\x05\x44\x65nom\x12\r\n\x05\x64\x65nom\x18\x01 \x01(\t\"\x81\x02\n\rDenomMetadata\x12\x13\n\x0b\x64\x65scription\x18\x01 \x01(\t\x12<\n\x0b\x64\x65nom_units\x18\x02 \x03(\x0b\x32\'.penumbra.core.asset.v1alpha1.DenomUnit\x12\x0c\n\x04\x62\x61se\x18\x03 \x01(\t\x12\x0f\n\x07\x64isplay\x18\x04 \x01(\t\x12\x0c\n\x04name\x18\x05 \x01(\t\x12\x0e\n\x06symbol\x18\x06 \x01(\t\x12\x0b\n\x03uri\x18\x07 \x01(\t\x12\x10\n\x08uri_hash\x18\x08 \x01(\t\x12\x41\n\x11penumbra_asset_id\x18\xc0\x0f \x01(\x0b\x32%.penumbra.core.asset.v1alpha1.AssetId\"=\n\tDenomUnit\x12\r\n\x05\x64\x65nom\x18\x01 \x01(\t\x12\x10\n\x08\x65xponent\x18\x02 \x01(\r\x12\x0f\n\x07\x61liases\x18\x03 \x03(\t\"t\n\x05Value\x12\x32\n\x06\x61mount\x18\x01 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\x12\x37\n\x08\x61sset_id\x18\x02 \x01(\x0b\x32%.penumbra.core.asset.v1alpha1.AssetId\"\xae\x03\n\tValueView\x12I\n\x0bknown_denom\x18\x01 \x01(\x0b\x32\x32.penumbra.core.asset.v1alpha1.ValueView.KnownDenomH\x00\x12M\n\runknown_denom\x18\x02 \x01(\x0b\x32\x34.penumbra.core.asset.v1alpha1.ValueView.UnknownDenomH\x00\x1a|\n\nKnownDenom\x12\x32\n\x06\x61mount\x18\x01 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\x12:\n\x05\x64\x65nom\x18\x02 \x01(\x0b\x32+.penumbra.core.asset.v1alpha1.DenomMetadata\x1a{\n\x0cUnknownDenom\x12\x32\n\x06\x61mount\x18\x01 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\x12\x37\n\x08\x61sset_id\x18\x02 \x01(\x0b\x32%.penumbra.core.asset.v1alpha1.AssetIdB\x0c\n\nvalue_viewb\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'penumbra.core.asset.v1alpha1.asset_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

    DESCRIPTOR._options = None
    _BALANCECOMMITMENT._serialized_start=112
    _BALANCECOMMITMENT._serialized_end=146
    _ASSETID._serialized_start=148
    _ASSETID._serialized_end=217
    _DENOM._serialized_start=219
    _DENOM._serialized_end=241
    _DENOMMETADATA._serialized_start=244
    _DENOMMETADATA._serialized_end=501
    _DENOMUNIT._serialized_start=503
    _DENOMUNIT._serialized_end=564
    _VALUE._serialized_start=566
    _VALUE._serialized_end=682
    _VALUEVIEW._serialized_start=685
    _VALUEVIEW._serialized_end=1115
    _VALUEVIEW_KNOWNDENOM._serialized_start=852
    _VALUEVIEW_KNOWNDENOM._serialized_end=976
    _VALUEVIEW_UNKNOWNDENOM._serialized_start=978
    _VALUEVIEW_UNKNOWNDENOM._serialized_end=1101
# @@protoc_insertion_point(module_scope)
