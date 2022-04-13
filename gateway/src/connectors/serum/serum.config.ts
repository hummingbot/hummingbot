import { ConfigManagerV2 } from '../../services/config-manager-v2';

export namespace SerumConfig {
  export interface Config {
    network: NetworkConfig;
  }

  export interface NetworkConfig {
    rpcURL: string;
  }

  export const config: Config = getSerumConfig();
}

export function getSerumConfig(): SerumConfig.Config {
  const configManager = ConfigManagerV2.getInstance();

  const prefix = 'serum';

  const network = configManager.get(`${prefix}.network`);

  return {
    network: {
      rpcURL: configManager.get(`${prefix}.networks.${network}.rpcURL`),
    }
  };
}
