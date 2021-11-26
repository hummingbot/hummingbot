import { TokenListType } from '../../services/base';
import { ConfigManagerV2 } from '../../services/config-manager-v2';
export interface NetworkConfig {
  chainID: number;
  nodeURL: string;
  tokenListType: TokenListType;
  tokenListSource: string;
}

export interface EthereumGasStationConfig {
  enabled: boolean;
  gasStationURL: string;
  APIKey: string;
  gasLevel: string;
  refreshTime: number;
  manualGasPrice: number;
}

export interface Config {
  mainnet: NetworkConfig;
  kovan: NetworkConfig;
  nodeAPIKey: string;
  nativeCurrencySymbol: string;
  network: string;
  ethereumGasStation: EthereumGasStationConfig;
}

ConfigManagerV2.setDefaults('ethereum', {
  networks: {
    mainnet: {
      chainID: 1,
      nodeURL: 'https://mainnet.infura.io/v3/',
      tokenListType: 'URL',
      tokenListSource:
        'https://wispy-bird-88a7.uniswap.workers.dev/?url=http://tokens.1inch.eth.link',
    },
    kovan: {
      chainID: 42,
      nodeURL: 'https://kovan.infura.io/v3/',
      tokenListType: 'FILE',
      tokenListSource: 'src/chains/ethereum/erc20_tokens_kovan.json',
    },
  },
  nativeCurrencySymbol: 'ETH',
  network: 'mainnet',
});

ConfigManagerV2.setDefaults('ethereum-gas-station', {
  enabled: true,
  gasStationURL: 'https://ethgasstation.info/api/ethgasAPI.json?api-key=',
  gasLevel: 'fast',
  refreshTime: 60,
  manualGasPrice: 100,
});
export namespace EthereumConfig {
  export const config: Config = {
    mainnet: {
      chainID: ConfigManagerV2.getInstance().get(
        'ethereum.networks.mainnet.chainID'
      ),
      nodeURL: ConfigManagerV2.getInstance().get(
        'ethereum.networks.mainnet.nodeURL'
      ),
      tokenListType: ConfigManagerV2.getInstance().get(
        'ethereum.networks.mainnet.tokenListType'
      ),
      tokenListSource: ConfigManagerV2.getInstance().get(
        'ethereum.networks.mainnet.tokenListSource'
      ),
    },
    kovan: {
      chainID: ConfigManagerV2.getInstance().get(
        'ethereum.networks.kovan.chainID'
      ),
      nodeURL: ConfigManagerV2.getInstance().get(
        'ethereum.networks.kovan.nodeURL'
      ),
      tokenListType: ConfigManagerV2.getInstance().get(
        'ethereum.networks.kovan.tokenListType'
      ),
      tokenListSource: ConfigManagerV2.getInstance().get(
        'ethereum.networks.kovan.tokenListSource'
      ),
    },
    nodeAPIKey: ConfigManagerV2.getInstance().get('ethereum.nodeAPIKey'),
    nativeCurrencySymbol: ConfigManagerV2.getInstance().get(
      'ethereum.nativeCurrencySymbol'
    ),
    network: ConfigManagerV2.getInstance().get('ethereum.network'),
    ethereumGasStation: {
      enabled: ConfigManagerV2.getInstance().get('ethereumGasStation.enabled'),
      gasStationURL: ConfigManagerV2.getInstance().get(
        'ethereumGasStation.gasStationURL'
      ),
      APIKey: ConfigManagerV2.getInstance().get('ethereumGasStation.APIKey'),
      gasLevel: ConfigManagerV2.getInstance().get(
        'ethereumGasStation.gasLevel'
      ),
      refreshTime: ConfigManagerV2.getInstance().get(
        'ethereumGasStation.refreshTime'
      ),
      manualGasPrice: ConfigManagerV2.getInstance().get(
        'ethereumGasStation.manualGasPrice'
      ),
    },
  };
}
