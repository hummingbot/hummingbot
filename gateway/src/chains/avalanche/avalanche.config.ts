import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { NetworkConfig } from '../ethereum/ethereum.config';

export interface AVConfig {
  fuji: NetworkConfig;
  avalanche: NetworkConfig;
}

ConfigManagerV2.setDefaults('avalanche', {
  networks: {
    fuji: {
      chainID: 43113,
      nodeURL: 'https://api.avax-test.network/ext/bc/C/rpc',
      tokenListType: 'FILE',
      tokenListSource: 'src/chains/avalanche/avalanche_tokens_fuji.json',
    },
    avalanche: {
      chainID: 43114,
      nodeURL:
        //'https://speedy-nodes-nyc.moralis.io/ac8325b518a591fe9d7f1820/avalanche/mainnet',
        'https://api.avax.network/ext/bc/C/rpc',
      tokenListType: 'URL',
      tokenListSource:
        'https://raw.githubusercontent.com/pangolindex/tokenlists/main/top15.tokenlist.json',
    },
  },
  nativeCurrencySymbol: 'AVAX',
  network: 'avalanche',
});

export namespace AvalancheConfig {
  export const config: AVConfig = {
    fuji: {
      chainID: 43113,
      nodeURL: 'https://api.avax-test.network/ext/bc/C/rpc',
      tokenListType: 'FILE',
      tokenListSource: 'src/chains/avalanche/avalanche_tokens_fuji.json',
    },
    avalanche: {
      chainID: 43114,
      nodeURL:
        //'https://speedy-nodes-nyc.moralis.io/ac8325b518a591fe9d7f1820/avalanche/mainnet',
        'https://api.avax.network/ext/bc/C/rpc',
      tokenListType: 'URL',
      tokenListSource:
        'https://raw.githubusercontent.com/pangolindex/tokenlists/main/top15.tokenlist.json',
    },
  };
}
