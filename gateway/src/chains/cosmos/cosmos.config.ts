import { TokenListType } from '../../services/base';
import { ConfigManagerV2 } from '../../services/config-manager-v2';
export interface NetworkConfig {
  name: string;
  rpcURL: string;
  tokenListType: TokenListType;
  tokenListSource: string;
}

export interface EthereumGasStationConfig {
  enabled: boolean;
  gasStationURL: string;
  APIKey: string;
  gasLevel: string;
  refreshTime: number;
}

export interface Config {
  network: NetworkConfig;
  nodeAPIKey: string;
  nativeCurrencySymbol: string;
  manualGasPrice: number;
}

export namespace CosmosConfig {
  export const config: Config = getCosmosConfig('cosmos', 'mainnet');
  export const ethGasStationConfig: EthereumGasStationConfig = {
    enabled: ConfigManagerV2.getInstance().get('ethereumGasStation.enabled'),
    gasStationURL: ConfigManagerV2.getInstance().get(
      'ethereumGasStation.gasStationURL'
    ),
    APIKey: ConfigManagerV2.getInstance().get('ethereumGasStation.APIKey'),
    gasLevel: ConfigManagerV2.getInstance().get('ethereumGasStation.gasLevel'),
    refreshTime: ConfigManagerV2.getInstance().get(
      'ethereumGasStation.refreshTime'
    ),
  };
}

export function getCosmosConfig(
  chainName: string,
  networkName: string
): Config {
  const network = networkName;
  // console.log(ConfigManagerV2.getInstance().get(chainName + '.nodeAPIKey'));
  return {
    network: {
      name: network,
      rpcURL: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.rpcURL'
      ),
      tokenListType: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.tokenListType'
      ),
      tokenListSource: ConfigManagerV2.getInstance().get(
        chainName + '.networks.' + network + '.tokenListSource'
      ),
    },
    nodeAPIKey: ConfigManagerV2.getInstance().get(chainName + '.nodeAPIKey'),
    nativeCurrencySymbol: ConfigManagerV2.getInstance().get(
      chainName + '.nativeCurrencySymbol'
    ),
    manualGasPrice: ConfigManagerV2.getInstance().get(
      chainName + '.manualGasPrice'
    ),
  };
}
