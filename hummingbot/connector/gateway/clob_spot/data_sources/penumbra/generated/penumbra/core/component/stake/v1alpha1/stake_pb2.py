# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: penumbra/core/component/stake/v1alpha1/stake.proto
"""Generated protocol buffer code."""
from google.protobuf import (
    descriptor as _descriptor,
    descriptor_pool as _descriptor_pool,
    symbol_database as _symbol_database,
)
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()

from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.asset.v1alpha1 import (
    asset_pb2 as penumbra_dot_core_dot_asset_dot_v1alpha1_dot_asset__pb2,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.keys.v1alpha1 import (
    keys_pb2 as penumbra_dot_core_dot_keys_dot_v1alpha1_dot_keys__pb2,
)
from hummingbot.connector.gateway.clob_spot.data_sources.penumbra.generated.penumbra.core.num.v1alpha1 import (
    num_pb2 as penumbra_dot_core_dot_num_dot_v1alpha1_dot_num__pb2,
)

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n2penumbra/core/component/stake/v1alpha1/stake.proto\x12&penumbra.core.component.stake.v1alpha1\x1a&penumbra/core/keys/v1alpha1/keys.proto\x1a$penumbra/core/num/v1alpha1/num.proto\x1a(penumbra/core/asset/v1alpha1/asset.proto\"\'\n\x16ZKUndelegateClaimProof\x12\r\n\x05inner\x18\x01 \x01(\x0c\"\xd4\x02\n\tValidator\x12>\n\x0cidentity_key\x18\x01 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x15\n\rconsensus_key\x18\x02 \x01(\x0c\x12\x0c\n\x04name\x18\x03 \x01(\t\x12\x0f\n\x07website\x18\x04 \x01(\t\x12\x13\n\x0b\x64\x65scription\x18\x05 \x01(\t\x12\x0f\n\x07\x65nabled\x18\x08 \x01(\x08\x12N\n\x0f\x66unding_streams\x18\x06 \x03(\x0b\x32\x35.penumbra.core.component.stake.v1alpha1.FundingStream\x12\x17\n\x0fsequence_number\x18\x07 \x01(\r\x12\x42\n\x0egovernance_key\x18\t \x01(\x0b\x32*.penumbra.core.keys.v1alpha1.GovernanceKey\"Q\n\rValidatorList\x12@\n\x0evalidator_keys\x18\x01 \x03(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\"\x8d\x02\n\rFundingStream\x12U\n\nto_address\x18\x01 \x01(\x0b\x32?.penumbra.core.component.stake.v1alpha1.FundingStream.ToAddressH\x00\x12M\n\x06to_dao\x18\x02 \x01(\x0b\x32;.penumbra.core.component.stake.v1alpha1.FundingStream.ToDaoH\x00\x1a.\n\tToAddress\x12\x0f\n\x07\x61\x64\x64ress\x18\x01 \x01(\t\x12\x10\n\x08rate_bps\x18\x02 \x01(\r\x1a\x19\n\x05ToDao\x12\x10\n\x08rate_bps\x18\x02 \x01(\rB\x0b\n\trecipient\"\x9f\x01\n\x08RateData\x12>\n\x0cidentity_key\x18\x01 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x13\n\x0b\x65poch_index\x18\x02 \x01(\x04\x12\x1d\n\x15validator_reward_rate\x18\x04 \x01(\x04\x12\x1f\n\x17validator_exchange_rate\x18\x05 \x01(\x04\"Y\n\x0c\x42\x61seRateData\x12\x13\n\x0b\x65poch_index\x18\x01 \x01(\x04\x12\x18\n\x10\x62\x61se_reward_rate\x18\x02 \x01(\x04\x12\x1a\n\x12\x62\x61se_exchange_rate\x18\x03 \x01(\x04\"\xfb\x01\n\x0fValidatorStatus\x12>\n\x0cidentity_key\x18\x01 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x45\n\x05state\x18\x02 \x01(\x0b\x32\x36.penumbra.core.component.stake.v1alpha1.ValidatorState\x12\x14\n\x0cvoting_power\x18\x03 \x01(\x04\x12K\n\rbonding_state\x18\x04 \x01(\x0b\x32\x34.penumbra.core.component.stake.v1alpha1.BondingState\"\x98\x02\n\x0c\x42ondingState\x12T\n\x05state\x18\x01 \x01(\x0e\x32\x45.penumbra.core.component.stake.v1alpha1.BondingState.BondingStateEnum\x12\x17\n\x0funbonding_epoch\x18\x02 \x01(\x04\"\x98\x01\n\x10\x42ondingStateEnum\x12\"\n\x1e\x42ONDING_STATE_ENUM_UNSPECIFIED\x10\x00\x12\x1d\n\x19\x42ONDING_STATE_ENUM_BONDED\x10\x01\x12 \n\x1c\x42ONDING_STATE_ENUM_UNBONDING\x10\x02\x12\x1f\n\x1b\x42ONDING_STATE_ENUM_UNBONDED\x10\x03\"\xd4\x02\n\x0eValidatorState\x12X\n\x05state\x18\x01 \x01(\x0e\x32I.penumbra.core.component.stake.v1alpha1.ValidatorState.ValidatorStateEnum\"\xe7\x01\n\x12ValidatorStateEnum\x12$\n VALIDATOR_STATE_ENUM_UNSPECIFIED\x10\x00\x12!\n\x1dVALIDATOR_STATE_ENUM_INACTIVE\x10\x01\x12\x1f\n\x1bVALIDATOR_STATE_ENUM_ACTIVE\x10\x02\x12\x1f\n\x1bVALIDATOR_STATE_ENUM_JAILED\x10\x03\x12#\n\x1fVALIDATOR_STATE_ENUM_TOMBSTONED\x10\x04\x12!\n\x1dVALIDATOR_STATE_ENUM_DISABLED\x10\x05\"\xe3\x01\n\rValidatorInfo\x12\x44\n\tvalidator\x18\x01 \x01(\x0b\x32\x31.penumbra.core.component.stake.v1alpha1.Validator\x12G\n\x06status\x18\x02 \x01(\x0b\x32\x37.penumbra.core.component.stake.v1alpha1.ValidatorStatus\x12\x43\n\trate_data\x18\x03 \x01(\x0b\x32\x30.penumbra.core.component.stake.v1alpha1.RateData\"m\n\x13ValidatorDefinition\x12\x44\n\tvalidator\x18\x01 \x01(\x0b\x32\x31.penumbra.core.component.stake.v1alpha1.Validator\x12\x10\n\x08\x61uth_sig\x18\x02 \x01(\x0c\"\xe1\x01\n\x08\x44\x65legate\x12\x44\n\x12validator_identity\x18\x01 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x13\n\x0b\x65poch_index\x18\x02 \x01(\x04\x12;\n\x0funbonded_amount\x18\x03 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\x12=\n\x11\x64\x65legation_amount\x18\x04 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\"\xe9\x01\n\nUndelegate\x12\x44\n\x12validator_identity\x18\x01 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x19\n\x11start_epoch_index\x18\x02 \x01(\x04\x12;\n\x0funbonded_amount\x18\x03 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\x12=\n\x11\x64\x65legation_amount\x18\x04 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\"k\n\x0fUndelegateClaim\x12I\n\x04\x62ody\x18\x01 \x01(\x0b\x32;.penumbra.core.component.stake.v1alpha1.UndelegateClaimBody\x12\r\n\x05proof\x18\x02 \x01(\x0c\"\x85\x02\n\x13UndelegateClaimBody\x12\x44\n\x12validator_identity\x18\x01 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x19\n\x11start_epoch_index\x18\x02 \x01(\x04\x12@\n\x07penalty\x18\x03 \x01(\x0b\x32/.penumbra.core.component.stake.v1alpha1.Penalty\x12K\n\x12\x62\x61lance_commitment\x18\x04 \x01(\x0b\x32/.penumbra.core.asset.v1alpha1.BalanceCommitment\"\xc4\x02\n\x13UndelegateClaimPlan\x12\x44\n\x12validator_identity\x18\x01 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x19\n\x11start_epoch_index\x18\x02 \x01(\x04\x12@\n\x07penalty\x18\x04 \x01(\x0b\x32/.penumbra.core.component.stake.v1alpha1.Penalty\x12<\n\x10unbonding_amount\x18\x05 \x01(\x0b\x32\".penumbra.core.num.v1alpha1.Amount\x12\x18\n\x10\x62\x61lance_blinding\x18\x06 \x01(\x0c\x12\x18\n\x10proof_blinding_r\x18\x07 \x01(\x0c\x12\x18\n\x10proof_blinding_s\x18\x08 \x01(\x0c\"\xa5\x01\n\x11\x44\x65legationChanges\x12\x45\n\x0b\x64\x65legations\x18\x01 \x03(\x0b\x32\x30.penumbra.core.component.stake.v1alpha1.Delegate\x12I\n\rundelegations\x18\x02 \x03(\x0b\x32\x32.penumbra.core.component.stake.v1alpha1.Undelegate\"H\n\x06Uptime\x12\x1a\n\x12\x61s_of_block_height\x18\x01 \x01(\x04\x12\x12\n\nwindow_len\x18\x02 \x01(\r\x12\x0e\n\x06\x62itvec\x18\x03 \x01(\x0c\"Y\n\x14\x43urrentConsensusKeys\x12\x41\n\x0e\x63onsensus_keys\x18\x01 \x03(\x0b\x32).penumbra.core.keys.v1alpha1.ConsensusKey\"\x18\n\x07Penalty\x12\r\n\x05inner\x18\x01 \x01(\x04\"?\n\x14ValidatorInfoRequest\x12\x10\n\x08\x63hain_id\x18\x01 \x01(\t\x12\x15\n\rshow_inactive\x18\x02 \x01(\x08\"f\n\x15ValidatorInfoResponse\x12M\n\x0evalidator_info\x18\x01 \x01(\x0b\x32\x35.penumbra.core.component.stake.v1alpha1.ValidatorInfo\"j\n\x16ValidatorStatusRequest\x12\x10\n\x08\x63hain_id\x18\x01 \x01(\t\x12>\n\x0cidentity_key\x18\x02 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\"b\n\x17ValidatorStatusResponse\x12G\n\x06status\x18\x01 \x01(\x0b\x32\x37.penumbra.core.component.stake.v1alpha1.ValidatorStatus\"\x9f\x01\n\x17ValidatorPenaltyRequest\x12\x10\n\x08\x63hain_id\x18\x01 \x01(\t\x12>\n\x0cidentity_key\x18\x02 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\x12\x19\n\x11start_epoch_index\x18\x03 \x01(\x04\x12\x17\n\x0f\x65nd_epoch_index\x18\x04 \x01(\x04\"\\\n\x18ValidatorPenaltyResponse\x12@\n\x07penalty\x18\x01 \x01(\x0b\x32/.penumbra.core.component.stake.v1alpha1.Penalty\"o\n\x1b\x43urrentValidatorRateRequest\x12\x10\n\x08\x63hain_id\x18\x01 \x01(\t\x12>\n\x0cidentity_key\x18\x02 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\"^\n\x1c\x43urrentValidatorRateResponse\x12>\n\x04\x64\x61ta\x18\x01 \x01(\x0b\x32\x30.penumbra.core.component.stake.v1alpha1.RateData\"l\n\x18NextValidatorRateRequest\x12\x10\n\x08\x63hain_id\x18\x01 \x01(\t\x12>\n\x0cidentity_key\x18\x02 \x01(\x0b\x32(.penumbra.core.keys.v1alpha1.IdentityKey\"[\n\x19NextValidatorRateResponse\x12>\n\x04\x64\x61ta\x18\x01 \x01(\x0b\x32\x30.penumbra.core.component.stake.v1alpha1.RateData\"\xef\x01\n\x0fStakeParameters\x12\x18\n\x10unbonding_epochs\x18\x01 \x01(\x04\x12\x1e\n\x16\x61\x63tive_validator_limit\x18\x02 \x01(\x04\x12\x18\n\x10\x62\x61se_reward_rate\x18\x03 \x01(\x04\x12$\n\x1cslashing_penalty_misbehavior\x18\x04 \x01(\x04\x12!\n\x19slashing_penalty_downtime\x18\x05 \x01(\x04\x12 \n\x18signed_blocks_window_len\x18\x06 \x01(\x04\x12\x1d\n\x15missed_blocks_maximum\x18\x07 \x01(\x04\"\xa6\x01\n\x0eGenesisContent\x12M\n\x0cstake_params\x18\x01 \x01(\x0b\x32\x37.penumbra.core.component.stake.v1alpha1.StakeParameters\x12\x45\n\nvalidators\x18\x02 \x03(\x0b\x32\x31.penumbra.core.component.stake.v1alpha1.Validator2\x8b\x06\n\x0cQueryService\x12\x8e\x01\n\rValidatorInfo\x12<.penumbra.core.component.stake.v1alpha1.ValidatorInfoRequest\x1a=.penumbra.core.component.stake.v1alpha1.ValidatorInfoResponse0\x01\x12\x92\x01\n\x0fValidatorStatus\x12>.penumbra.core.component.stake.v1alpha1.ValidatorStatusRequest\x1a?.penumbra.core.component.stake.v1alpha1.ValidatorStatusResponse\x12\x95\x01\n\x10ValidatorPenalty\x12?.penumbra.core.component.stake.v1alpha1.ValidatorPenaltyRequest\x1a@.penumbra.core.component.stake.v1alpha1.ValidatorPenaltyResponse\x12\xa1\x01\n\x14\x43urrentValidatorRate\x12\x43.penumbra.core.component.stake.v1alpha1.CurrentValidatorRateRequest\x1a\x44.penumbra.core.component.stake.v1alpha1.CurrentValidatorRateResponse\x12\x98\x01\n\x11NextValidatorRate\x12@.penumbra.core.component.stake.v1alpha1.NextValidatorRateRequest\x1a\x41.penumbra.core.component.stake.v1alpha1.NextValidatorRateResponseb\x06proto3'
)

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, 'penumbra.core.component.stake.v1alpha1.stake_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

    DESCRIPTOR._options = None
    _ZKUNDELEGATECLAIMPROOF._serialized_start = 214
    _ZKUNDELEGATECLAIMPROOF._serialized_end = 253
    _VALIDATOR._serialized_start = 256
    _VALIDATOR._serialized_end = 596
    _VALIDATORLIST._serialized_start = 598
    _VALIDATORLIST._serialized_end = 679
    _FUNDINGSTREAM._serialized_start = 682
    _FUNDINGSTREAM._serialized_end = 951
    _FUNDINGSTREAM_TOADDRESS._serialized_start = 865
    _FUNDINGSTREAM_TOADDRESS._serialized_end = 911
    _FUNDINGSTREAM_TODAO._serialized_start = 913
    _FUNDINGSTREAM_TODAO._serialized_end = 938
    _RATEDATA._serialized_start = 954
    _RATEDATA._serialized_end = 1113
    _BASERATEDATA._serialized_start = 1115
    _BASERATEDATA._serialized_end = 1204
    _VALIDATORSTATUS._serialized_start = 1207
    _VALIDATORSTATUS._serialized_end = 1458
    _BONDINGSTATE._serialized_start = 1461
    _BONDINGSTATE._serialized_end = 1741
    _BONDINGSTATE_BONDINGSTATEENUM._serialized_start = 1589
    _BONDINGSTATE_BONDINGSTATEENUM._serialized_end = 1741
    _VALIDATORSTATE._serialized_start = 1744
    _VALIDATORSTATE._serialized_end = 2084
    _VALIDATORSTATE_VALIDATORSTATEENUM._serialized_start = 1853
    _VALIDATORSTATE_VALIDATORSTATEENUM._serialized_end = 2084
    _VALIDATORINFO._serialized_start = 2087
    _VALIDATORINFO._serialized_end = 2314
    _VALIDATORDEFINITION._serialized_start = 2316
    _VALIDATORDEFINITION._serialized_end = 2425
    _DELEGATE._serialized_start = 2428
    _DELEGATE._serialized_end = 2653
    _UNDELEGATE._serialized_start = 2656
    _UNDELEGATE._serialized_end = 2889
    _UNDELEGATECLAIM._serialized_start = 2891
    _UNDELEGATECLAIM._serialized_end = 2998
    _UNDELEGATECLAIMBODY._serialized_start = 3001
    _UNDELEGATECLAIMBODY._serialized_end = 3262
    _UNDELEGATECLAIMPLAN._serialized_start = 3265
    _UNDELEGATECLAIMPLAN._serialized_end = 3589
    _DELEGATIONCHANGES._serialized_start = 3592
    _DELEGATIONCHANGES._serialized_end = 3757
    _UPTIME._serialized_start = 3759
    _UPTIME._serialized_end = 3831
    _CURRENTCONSENSUSKEYS._serialized_start = 3833
    _CURRENTCONSENSUSKEYS._serialized_end = 3922
    _PENALTY._serialized_start = 3924
    _PENALTY._serialized_end = 3948
    _VALIDATORINFOREQUEST._serialized_start = 3950
    _VALIDATORINFOREQUEST._serialized_end = 4013
    _VALIDATORINFORESPONSE._serialized_start = 4015
    _VALIDATORINFORESPONSE._serialized_end = 4117
    _VALIDATORSTATUSREQUEST._serialized_start = 4119
    _VALIDATORSTATUSREQUEST._serialized_end = 4225
    _VALIDATORSTATUSRESPONSE._serialized_start = 4227
    _VALIDATORSTATUSRESPONSE._serialized_end = 4325
    _VALIDATORPENALTYREQUEST._serialized_start = 4328
    _VALIDATORPENALTYREQUEST._serialized_end = 4487
    _VALIDATORPENALTYRESPONSE._serialized_start = 4489
    _VALIDATORPENALTYRESPONSE._serialized_end = 4581
    _CURRENTVALIDATORRATEREQUEST._serialized_start = 4583
    _CURRENTVALIDATORRATEREQUEST._serialized_end = 4694
    _CURRENTVALIDATORRATERESPONSE._serialized_start = 4696
    _CURRENTVALIDATORRATERESPONSE._serialized_end = 4790
    _NEXTVALIDATORRATEREQUEST._serialized_start = 4792
    _NEXTVALIDATORRATEREQUEST._serialized_end = 4900
    _NEXTVALIDATORRATERESPONSE._serialized_start = 4902
    _NEXTVALIDATORRATERESPONSE._serialized_end = 4993
    _STAKEPARAMETERS._serialized_start = 4996
    _STAKEPARAMETERS._serialized_end = 5235
    _GENESISCONTENT._serialized_start = 5238
    _GENESISCONTENT._serialized_end = 5404
    _QUERYSERVICE._serialized_start = 5407
    _QUERYSERVICE._serialized_end = 6186
# @@protoc_insertion_point(module_scope)