# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: cosmos/ics23/v1/proofs.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1c\x63osmos/ics23/v1/proofs.proto\x12\x0f\x63osmos.ics23.v1\"{\n\x0e\x45xistenceProof\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\r\n\x05value\x18\x02 \x01(\x0c\x12%\n\x04leaf\x18\x03 \x01(\x0b\x32\x17.cosmos.ics23.v1.LeafOp\x12&\n\x04path\x18\x04 \x03(\x0b\x32\x18.cosmos.ics23.v1.InnerOp\"\x7f\n\x11NonExistenceProof\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12-\n\x04left\x18\x02 \x01(\x0b\x32\x1f.cosmos.ics23.v1.ExistenceProof\x12.\n\x05right\x18\x03 \x01(\x0b\x32\x1f.cosmos.ics23.v1.ExistenceProof\"\xef\x01\n\x0f\x43ommitmentProof\x12\x30\n\x05\x65xist\x18\x01 \x01(\x0b\x32\x1f.cosmos.ics23.v1.ExistenceProofH\x00\x12\x36\n\x08nonexist\x18\x02 \x01(\x0b\x32\".cosmos.ics23.v1.NonExistenceProofH\x00\x12,\n\x05\x62\x61tch\x18\x03 \x01(\x0b\x32\x1b.cosmos.ics23.v1.BatchProofH\x00\x12;\n\ncompressed\x18\x04 \x01(\x0b\x32%.cosmos.ics23.v1.CompressedBatchProofH\x00\x42\x07\n\x05proof\"\xc8\x01\n\x06LeafOp\x12%\n\x04hash\x18\x01 \x01(\x0e\x32\x17.cosmos.ics23.v1.HashOp\x12,\n\x0bprehash_key\x18\x02 \x01(\x0e\x32\x17.cosmos.ics23.v1.HashOp\x12.\n\rprehash_value\x18\x03 \x01(\x0e\x32\x17.cosmos.ics23.v1.HashOp\x12)\n\x06length\x18\x04 \x01(\x0e\x32\x19.cosmos.ics23.v1.LengthOp\x12\x0e\n\x06prefix\x18\x05 \x01(\x0c\"P\n\x07InnerOp\x12%\n\x04hash\x18\x01 \x01(\x0e\x32\x17.cosmos.ics23.v1.HashOp\x12\x0e\n\x06prefix\x18\x02 \x01(\x0c\x12\x0e\n\x06suffix\x18\x03 \x01(\x0c\"\x8d\x01\n\tProofSpec\x12*\n\tleaf_spec\x18\x01 \x01(\x0b\x32\x17.cosmos.ics23.v1.LeafOp\x12.\n\ninner_spec\x18\x02 \x01(\x0b\x32\x1a.cosmos.ics23.v1.InnerSpec\x12\x11\n\tmax_depth\x18\x03 \x01(\x05\x12\x11\n\tmin_depth\x18\x04 \x01(\x05\"\xa6\x01\n\tInnerSpec\x12\x13\n\x0b\x63hild_order\x18\x01 \x03(\x05\x12\x12\n\nchild_size\x18\x02 \x01(\x05\x12\x19\n\x11min_prefix_length\x18\x03 \x01(\x05\x12\x19\n\x11max_prefix_length\x18\x04 \x01(\x05\x12\x13\n\x0b\x65mpty_child\x18\x05 \x01(\x0c\x12%\n\x04hash\x18\x06 \x01(\x0e\x32\x17.cosmos.ics23.v1.HashOp\":\n\nBatchProof\x12,\n\x07\x65ntries\x18\x01 \x03(\x0b\x32\x1b.cosmos.ics23.v1.BatchEntry\"\x7f\n\nBatchEntry\x12\x30\n\x05\x65xist\x18\x01 \x01(\x0b\x32\x1f.cosmos.ics23.v1.ExistenceProofH\x00\x12\x36\n\x08nonexist\x18\x02 \x01(\x0b\x32\".cosmos.ics23.v1.NonExistenceProofH\x00\x42\x07\n\x05proof\"\x7f\n\x14\x43ompressedBatchProof\x12\x36\n\x07\x65ntries\x18\x01 \x03(\x0b\x32%.cosmos.ics23.v1.CompressedBatchEntry\x12/\n\rlookup_inners\x18\x02 \x03(\x0b\x32\x18.cosmos.ics23.v1.InnerOp\"\x9d\x01\n\x14\x43ompressedBatchEntry\x12:\n\x05\x65xist\x18\x01 \x01(\x0b\x32).cosmos.ics23.v1.CompressedExistenceProofH\x00\x12@\n\x08nonexist\x18\x02 \x01(\x0b\x32,.cosmos.ics23.v1.CompressedNonExistenceProofH\x00\x42\x07\n\x05proof\"k\n\x18\x43ompressedExistenceProof\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\r\n\x05value\x18\x02 \x01(\x0c\x12%\n\x04leaf\x18\x03 \x01(\x0b\x32\x17.cosmos.ics23.v1.LeafOp\x12\x0c\n\x04path\x18\x04 \x03(\x05\"\x9d\x01\n\x1b\x43ompressedNonExistenceProof\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\x37\n\x04left\x18\x02 \x01(\x0b\x32).cosmos.ics23.v1.CompressedExistenceProof\x12\x38\n\x05right\x18\x03 \x01(\x0b\x32).cosmos.ics23.v1.CompressedExistenceProof*e\n\x06HashOp\x12\x0b\n\x07NO_HASH\x10\x00\x12\n\n\x06SHA256\x10\x01\x12\n\n\x06SHA512\x10\x02\x12\n\n\x06KECCAK\x10\x03\x12\r\n\tRIPEMD160\x10\x04\x12\x0b\n\x07\x42ITCOIN\x10\x05\x12\x0e\n\nSHA512_256\x10\x06*\xab\x01\n\x08LengthOp\x12\r\n\tNO_PREFIX\x10\x00\x12\r\n\tVAR_PROTO\x10\x01\x12\x0b\n\x07VAR_RLP\x10\x02\x12\x0f\n\x0b\x46IXED32_BIG\x10\x03\x12\x12\n\x0e\x46IXED32_LITTLE\x10\x04\x12\x0f\n\x0b\x46IXED64_BIG\x10\x05\x12\x12\n\x0e\x46IXED64_LITTLE\x10\x06\x12\x14\n\x10REQUIRE_32_BYTES\x10\x07\x12\x14\n\x10REQUIRE_64_BYTES\x10\x08\x42\"Z github.com/cosmos/ics23/go;ics23b\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'cosmos.ics23.v1.proofs_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'Z github.com/cosmos/ics23/go;ics23'
  _HASHOP._serialized_start=1890
  _HASHOP._serialized_end=1991
  _LENGTHOP._serialized_start=1994
  _LENGTHOP._serialized_end=2165
  _EXISTENCEPROOF._serialized_start=49
  _EXISTENCEPROOF._serialized_end=172
  _NONEXISTENCEPROOF._serialized_start=174
  _NONEXISTENCEPROOF._serialized_end=301
  _COMMITMENTPROOF._serialized_start=304
  _COMMITMENTPROOF._serialized_end=543
  _LEAFOP._serialized_start=546
  _LEAFOP._serialized_end=746
  _INNEROP._serialized_start=748
  _INNEROP._serialized_end=828
  _PROOFSPEC._serialized_start=831
  _PROOFSPEC._serialized_end=972
  _INNERSPEC._serialized_start=975
  _INNERSPEC._serialized_end=1141
  _BATCHPROOF._serialized_start=1143
  _BATCHPROOF._serialized_end=1201
  _BATCHENTRY._serialized_start=1203
  _BATCHENTRY._serialized_end=1330
  _COMPRESSEDBATCHPROOF._serialized_start=1332
  _COMPRESSEDBATCHPROOF._serialized_end=1459
  _COMPRESSEDBATCHENTRY._serialized_start=1462
  _COMPRESSEDBATCHENTRY._serialized_end=1619
  _COMPRESSEDEXISTENCEPROOF._serialized_start=1621
  _COMPRESSEDEXISTENCEPROOF._serialized_end=1728
  _COMPRESSEDNONEXISTENCEPROOF._serialized_start=1731
  _COMPRESSEDNONEXISTENCEPROOF._serialized_end=1888
# @@protoc_insertion_point(module_scope)