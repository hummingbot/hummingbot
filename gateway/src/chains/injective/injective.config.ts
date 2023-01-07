import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { getNetworkFromString } from './injective.mappers';
import { getNetworkEndpoints } from '@injectivelabs/networks';

export interface NetworkConfig {
  name: string;
  nodeURL: string;
  chainId: string;
  maxLRUCacheInstances: number;
}

export interface Config {
  network: NetworkConfig;
  nativeCurrencySymbol: string;
}

export function getInjectiveConfig(networkName: string): Config {
  const network = getNetworkFromString(networkName);
  return {
    network: {
      name: networkName,
      chainId: ConfigManagerV2.getInstance().get(
        'injective.networks.' + networkName + '.chainId'
      ),
      nodeURL: network ? getNetworkEndpoints(network).indexer : '',
      maxLRUCacheInstances: 10,
    },
    nativeCurrencySymbol: ConfigManagerV2.getInstance().get(
      'injective.nativeCurrencySymbol'
    ),
  };
}
