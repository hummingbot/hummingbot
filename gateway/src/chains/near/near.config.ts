import { TokenListType } from '../../services/base';
import { ConfigManagerV2 } from '../../services/config-manager-v2';

export interface NetworkConfig {
  name: string;
  nodeURL: string;
  tokenListType: TokenListType;
  tokenListSource: string;
  gasPriceRefreshInterval: number | undefined;
}

export interface Config {
  network: NetworkConfig;
  nativeCurrencySymbol: string;
  manualGasPrice: number;
  gasLimitTransaction: number;
}

export function getNearConfig(chainName: string, networkName: string): Config {
  const network = networkName;
  return {
    network: {
      name: network,
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
