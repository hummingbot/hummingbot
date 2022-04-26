export default {
  solana: {
    network: 'mainnet-beta',
    wallet: {
      owner: {
        address: '3skU2fVbR4iV3nkSYmKSFsn2VwM1GzSp9QfWQmsnZJdy',
        // address: '8wvTyrdGmrjFUAdg4yHoBtPu9eE41t8fxruxTh7ufMkQ',
      },
      payer: {
        // address: '3skU2fVbR4iV3nkSYmKSFsn2VwM1GzSp9QfWQmsnZJdy',
        address: '8wvTyrdGmrjFUAdg4yHoBtPu9eE41t8fxruxTh7ufMkQ',
      },
    }
  },
  serum: {
    chain: 'solana',
    network: 'mainnet-beta',
    connector: 'serum',
  },
};
