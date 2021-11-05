import { NetworkConfig } from '../ethereum/ethereum.config';

export interface AVConfig {
  fuji: NetworkConfig;
  avalanche: NetworkConfig;
}

export namespace AvalancheConfig {
  export const config: AVConfig = {
    fuji: {
      chainId: 43113,
      rpcUrl: 'https://api.avax-test.network/ext/bc/C/rpc',
      tokenListType: 'FILE',
      tokenListSource: 'src/chains/avalanche/avalanche_tokens_fuji.json',
    },
    avalanche: {
      chainId: 43114,
      rpcUrl:
        //'https://speedy-nodes-nyc.moralis.io/ac8325b518a591fe9d7f1820/avalanche/mainnet',
        'https://api.avax.network/ext/bc/C/rpc',
      tokenListType: 'URL',
      tokenListSource:
        'https://raw.githubusercontent.com/pangolindex/tokenlists/main/top15.tokenlist.json',
    },
  };
}
