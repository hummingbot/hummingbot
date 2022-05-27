export default {
  solana: {
    wallet: {
      owner: {
        publicKey: 'FMosjpvtAxwL6GFDSL31o9pU5somKjifbkt32bEgLddf',
        privateKey:
          '3mFmUEqdf86r7VEs8gCAHaEZ2gBmXzpgVPPjQ71fbMDYejso3Qqd18AgnkUbyqFyHrCDC7BUJLSXRqZuLK7Bd9yP',
      },
      payer: {
        'SOL/USDT': {
          publicKey: 'AMosjpvtAxwL6GFDSL31o9pU5somKjifbkt32bEgLddf',
        },
        'SOL/USDC': {
          publicKey: 'BMosjpvtAxwL6GFDSL31o9pU5somKjifbkt32bEgLddf',
        },
      },
    },
    markets: {
      'SOL/USDT': {
        name: 'SOL/USDT',
        address: 'HWHvQhFmJB3NUcu1aihKmrKegfVxBEHzwVX6yZCKEsi1',
      },
      'SOL/USDC': {
        name: 'SOL/USDC',
        address: '9wFFyRfZBsuAha4YcuxcXLKwMxJR43S7fPfQLusDBzvT',
      },
      'SRM/SOL': {
        name: 'SRM/SOL',
        address: 'jyei9Fpj2GtHLDDGgcuhDacxYLLiSyxU4TY7KxB2xai',
      },
    },
  },
  serum: {
    chain: 'solana',
    network: 'mainnet-beta',
    connector: 'serum',
  },
};
