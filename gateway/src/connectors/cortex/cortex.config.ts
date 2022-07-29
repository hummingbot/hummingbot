import { AvailableNetworks } from '../../services/config-manager-types';

export namespace CortexConfig {
  export interface NetworkConfig {
    availableNetworks: Array<AvailableNetworks>;
    tradingTypes: Array<string>;
  }

  export const config: NetworkConfig = {
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [{ chain: 'ethereum', networks: ['mainnet'] }],
  };
}
