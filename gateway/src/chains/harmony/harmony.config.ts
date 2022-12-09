import { TokenListType } from '../../services/base';
import { ConfigManagerV2 } from '../../services/config-manager-v2';
interface NetworkConfig {
  name: string;
  chainID: number;
  nodeURL: string;
  tokenListType: TokenListType;
  tokenListSource: string;
}

interface Config {
  network: NetworkConfig;
  nativeCurrencySymbol: string;
  autoGasPrice: boolean;
  manualGasPrice: number;
  gasPricerefreshTime: number;
  gasLimitTransaction: number;
}

export function getHarmonyConfig(
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
    },
    nativeCurrencySymbol: ConfigManagerV2.getInstance().get(
      chainName + '.networks.' + network + '.nativeCurrencySymbol'
    ),
    autoGasPrice: ConfigManagerV2.getInstance().get(
      chainName + '.autoGasPrice'
    ),
    manualGasPrice: ConfigManagerV2.getInstance().get(
      chainName + '.manualGasPrice'
    ),
    gasPricerefreshTime: ConfigManagerV2.getInstance().get(
      chainName + '.gasPricerefreshTime'
    ),
    gasLimitTransaction: ConfigManagerV2.getInstance().get(
      chainName + '.gasLimitTransaction'
    ),
  };
}
