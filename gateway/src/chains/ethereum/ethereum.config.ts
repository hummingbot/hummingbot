import { TokenListType } from '../../services/base';
import { ConfigManagerV2 } from '../../services/config-manager-v2';
export interface NetworkConfig {
  name: string;
  chainID: number;
  nodeURL: string;
  tokenListType: TokenListType;
  tokenListSource: string;
  gasPriceRefreshInterval: number | undefined;
}

export interface EthereumGasStationConfig {
  enabled: boolean;
  gasStationURL: string;
  APIKey: string;
  gasLevel: string;
}

export interface Config {
  network: NetworkConfig;
  nativeCurrencySymbol: string;
  manualGasPrice: number;
  gasLimitTransaction: number;
}

export namespace EthereumConfig {
  export const ethGasStationConfig: EthereumGasStationConfig = {
    enabled: ConfigManagerV2.getInstance().get('ethereumGasStation.enabled'),
    gasStationURL: ConfigManagerV2.getInstance().get(
      'ethereumGasStation.gasStationURL'
    ),
    APIKey: ConfigManagerV2.getInstance().get('ethereumGasStation.APIKey'),
    gasLevel: ConfigManagerV2.getInstance().get('ethereumGasStation.gasLevel'),
  };
}

export function getEthereumConfig(
  chainName: string,
  networkName: string
): Config {
  const network = networkName;
  return {
    network: {
      name: network,
      chainID: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.chainID'
      ),
      nodeURL: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.nodeURL'
      ),
      tokenListType: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.tokenListType'
      ),
      tokenListSource: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.tokenListSource'
      ),
      gasPriceRefreshInterval: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.gasPriceRefreshInterval'
      ),
    },
    nativeCurrencySymbol: ConfigManagerV2.getInstance().get(
      chainName + '.networks.' + network + '.nativeCurrencySymbol'
    ),
    manualGasPrice: ConfigManagerV2.getInstance().get(
      chainName + '.manualGasPrice'
    ),
    gasLimitTransaction: ConfigManagerV2.getInstance().get(
      chainName + '.gasLimitTransaction'
    ),
  };
}
