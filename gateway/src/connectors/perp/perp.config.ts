import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace PerpConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    ttl: number;
    tradingTypes: (type: string) => Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(`perp.allowedSlippage`),
    ttl: ConfigManagerV2.getInstance().get(`perp.versions.ttl`),
    tradingTypes: (type: string) =>
      type === 'perp' ? ['EVM_Perpetual'] : ['EVM_AMM_LP'],
    availableNetworks: [{ chain: 'ethereum', networks: ['optimism'] }],
  };
}
