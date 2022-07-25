import { AvailableNetworks } from '../../services/config-manager-types';

export namespace CortexConfig {
  export interface NetworkConfig {
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    availableNetworks: [{ chain: 'ethereum', networks: ['mainnet'] }],
  };
}
