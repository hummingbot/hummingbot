import { PublicKey } from '@solana/web3.js';

export default {
  account: {
    data: {
      program: 'spl-token',
      parsed: {
        accountType: 'account',
        info: {
          tokenAmount: {
            amount: '1',
            decimals: 1,
            uiAmount: 0.1,
            uiAmountString: '0.1',
          },
          delegate: new PublicKey(
            '4Nd1mBQtrMJVYVfKf2PJy9NZUZdTAsp7D4xWLs4gDB4T'
          ),
          delegatedAmount: {
            amount: '1',
            decimals: 1,
            uiAmount: 0.1,
            uiAmountString: '0.1',
          },
          state: 'initialized',
          isNative: false,
          mint: new PublicKey('3wyAj7Rt1TWVPZVteFJPLa26JmLvdb1CAKEFZm3NY75E'),
          owner: new PublicKey('4Qkev8aNZcqFNSRhQzwyLMFSsi94jHqE8WNVTJzTP99F'),
        },
        type: 'account',
      },
      space: 165,
    },
    executable: false,
    lamports: 1726080,
    owner: new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'),
    rentEpoch: 4,
  },
  pubkey: new PublicKey('C2gJg6tKpQs41PRS1nC8aw3ZKNZK3HQQZGVrDFDup5nx'),
};
