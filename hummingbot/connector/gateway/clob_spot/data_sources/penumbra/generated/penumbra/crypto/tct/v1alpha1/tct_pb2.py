# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: penumbra/crypto/tct/v1alpha1/tct.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n&penumbra/crypto/tct/v1alpha1/tct.proto\x12\x1cpenumbra.crypto.tct.v1alpha1\" \n\x0fStateCommitment\x12\r\n\x05inner\x18\x01 \x01(\x0c\"\x1b\n\nMerkleRoot\x12\r\n\x05inner\x18\x01 \x01(\x0c\"\xb2\x01\n\x14StateCommitmentProof\x12\x46\n\x0fnote_commitment\x18\x01 \x01(\x0b\x32-.penumbra.crypto.tct.v1alpha1.StateCommitment\x12\x10\n\x08position\x18\x02 \x01(\x04\x12@\n\tauth_path\x18\x03 \x03(\x0b\x32-.penumbra.crypto.tct.v1alpha1.MerklePathChunk\"J\n\x0fMerklePathChunk\x12\x11\n\tsibling_1\x18\x01 \x01(\x0c\x12\x11\n\tsibling_2\x18\x02 \x01(\x0c\x12\x11\n\tsibling_3\x18\x03 \x01(\x0c\x62\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'penumbra.crypto.tct.v1alpha1.tct_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _STATECOMMITMENT._serialized_start=72
  _STATECOMMITMENT._serialized_end=104
  _MERKLEROOT._serialized_start=106
  _MERKLEROOT._serialized_end=133
  _STATECOMMITMENTPROOF._serialized_start=136
  _STATECOMMITMENTPROOF._serialized_end=314
  _MERKLEPATHCHUNK._serialized_start=316
  _MERKLEPATHCHUNK._serialized_end=390
# @@protoc_insertion_point(module_scope)