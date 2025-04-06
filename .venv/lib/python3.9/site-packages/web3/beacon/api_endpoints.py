# [ BEACON endpoints ]

GET_GENESIS = "/eth/v1/beacon/genesis"

# states
GET_HASH_ROOT = "/eth/v1/beacon/states/{0}/root"
GET_FORK_DATA = "/eth/v1/beacon/states/{0}/fork"
GET_FINALITY_CHECKPOINT = "/eth/v1/beacon/states/{0}/finality_checkpoints"
GET_VALIDATORS = "/eth/v1/beacon/states/{0}/validators"
GET_VALIDATOR = "/eth/v1/beacon/states/{0}/validators/{1}"
GET_VALIDATOR_BALANCES = "/eth/v1/beacon/states/{0}/validator_balances"
GET_EPOCH_COMMITTEES = "/eth/v1/beacon/states/{0}/committees"
GET_EPOCH_SYNC_COMMITTEES = "/eth/v1/beacon/states/{0}/sync_committees"
GET_EPOCH_RANDAO = "/eth/v1/beacon/states/{0}/randao"

# headers
GET_BLOCK_HEADERS = "/eth/v1/beacon/headers"
GET_BLOCK_HEADER = "/eth/v1/beacon/headers/{0}"

# blocks
GET_BLOCK = "/eth/v2/beacon/blocks/{0}"
GET_BLOCK_ROOT = "/eth/v1/beacon/blocks/{0}/root"
GET_BLOCK_ATTESTATIONS = "/eth/v1/beacon/blocks/{0}/attestations"
GET_BLINDED_BLOCKS = "/eth/v1/beacon/blinded_blocks/{0}"

# rewards
GET_REWARDS = "/eth/v1/beacon/rewards/blocks/{0}"

# blobs
GET_BLOB_SIDECARS = "/eth/v1/beacon/blob_sidecars/{0}"

# light client
GET_LIGHT_CLIENT_BOOTSTRAP_STRUCTURE = "/eth/v1/beacon/light_client/bootstrap/{0}"
GET_LIGHT_CLIENT_UPDATES = "/eth/v1/beacon/light_client/updates"
GET_LIGHT_CLIENT_FINALITY_UPDATE = "/eth/v1/beacon/light_client/finality_update"
GET_LIGHT_CLIENT_OPTIMISTIC_UPDATE = "/eth/v1/beacon/light_client/optimistic_update"

# pool
GET_ATTESTATIONS = "/eth/v1/beacon/pool/attestations"
GET_ATTESTER_SLASHINGS = "/eth/v1/beacon/pool/attester_slashings"
GET_PROPOSER_SLASHINGS = "/eth/v1/beacon/pool/proposer_slashings"
GET_VOLUNTARY_EXITS = "/eth/v1/beacon/pool/voluntary_exits"
GET_BLS_TO_EXECUTION_CHANGES = "/eth/v1/beacon/pool/bls_to_execution_changes"


# [ CONFIG endpoints ]

GET_FORK_SCHEDULE = "/eth/v1/config/fork_schedule"
GET_SPEC = "/eth/v1/config/spec"
GET_DEPOSIT_CONTRACT = "/eth/v1/config/deposit_contract"

# [ DEBUG endpoints ]

GET_BEACON_STATE = "/eth/v1/debug/beacon/states/{0}"
GET_BEACON_HEADS = "/eth/v1/debug/beacon/heads"

# [ NODE endpoints ]

GET_NODE_IDENTITY = "/eth/v1/node/identity"
GET_PEERS = "/eth/v1/node/peers"
GET_PEER = "/eth/v1/node/peers/{0}"
GET_PEER_COUNT = "/eth/v1/node/peer_count"
GET_HEALTH = "/eth/v1/node/health"
GET_VERSION = "/eth/v1/node/version"
GET_SYNCING = "/eth/v1/node/syncing"

# [ VALIDATOR endpoints ]

GET_ATTESTER_DUTIES = "/eth/v1/validator/duties/attester/{0}"
GET_BLOCK_PROPOSERS_DUTIES = "/eth/v1/validator/duties/proposer/{0}"
GET_SYNC_COMMITTEE_DUTIES = "/eth/v1/validator/duties/sync/{0}"

# [ REWARDS endpoints ]
GET_ATTESTATIONS_REWARDS = "/eth/v1/beacon/rewards/attestations/{0}"
