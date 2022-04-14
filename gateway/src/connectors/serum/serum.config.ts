import { ConfigManagerV2 } from '../../services/config-manager-v2';

export namespace SerumConfig {
  export interface Config {
    network: NetworkConfig;
  }

  export interface NetworkConfig {
    rpcURL: string;
  }
}

export function getSerumConfig(network: string): SerumConfig.Config {
  const configManager = ConfigManagerV2.getInstance();

  const prefix = 'serum';

  const targetNetwork = network || configManager.get(`${prefix}.network`);

  return {
    network: {
      rpcURL: configManager.get(`${prefix}.networks.${targetNetwork}.rpcURL`),
    }
  };
}
