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
  },
  serum: {
    chain: 'solana',
    network: 'mainnet-beta',
    connector: 'serum',
  },
};
