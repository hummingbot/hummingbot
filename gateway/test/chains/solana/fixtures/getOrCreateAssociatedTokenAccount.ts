import { PublicKey } from '@solana/web3.js';
import BN from 'bn.js';

export default {
  address: new PublicKey('C2gJg6tKpQs41PRS1nC8aw3ZKNZK3HQQZGVrDFDup5nx'),
  mint: new PublicKey('3wyAj7Rt1TWVPZVteFJPLa26JmLvdb1CAKEFZm3NY75E'),
  owner: new PublicKey('4Qkev8aNZcqFNSRhQzwyLMFSsi94jHqE8WNVTJzTP99F'),
  amount: new BN(1),
  delegate: new PublicKey('4Nd1mBQtrMJVYVfKf2PJy9NZUZdTAsp7D4xWLs4gDB4T'),
  delegatedAmount: new BN(1),
  isInitialized: true,
  isFrozen: false,
  isNative: false,
  rentExemptReserve: null,
  closeAuthority: new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'),
};
