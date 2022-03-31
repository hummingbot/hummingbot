import { ConfigManagerV2 } from '../../services/config-manager-v2';

export namespace SerumConfig {
  export interface Config {
    network: NetworkConfig;
    allowedSlippage: string;
    ttl: number;
  }

  export interface NetworkConfig {
    slug: string;
    rpcUrl: string;
  }

  export const config: Config = getSerumConfig('serum');
}

export function getSerumConfig(chainName: string): SerumConfig.Config {
  const configManager = ConfigManagerV2.getInstance();

  const network = configManager.get(`${chainName}.network`);

  return {
    network: {
      slug: network,
      rpcUrl: configManager.get(`${chainName}.networks.${network}.rpcURL`),
    },
    allowedSlippage: configManager.get(`${chainName}.allowedSlippage`),
    ttl: configManager.get(`${chainName}.ttl`),
  };
}
