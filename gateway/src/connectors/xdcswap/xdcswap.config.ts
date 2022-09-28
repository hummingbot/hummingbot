import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace XdcswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimitEstimate: number;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get('xdcswap.allowedSlippage'),
    gasLimitEstimate: ConfigManagerV2.getInstance().get('xdcswap.gasLimitEstimate'),
    ttl: ConfigManagerV2.getInstance().get('xdcswap.ttl'),
    routerAddress: (network: string) => ConfigManagerV2.getInstance().get('xdcswap.contractAddresses.' + network + '.routerAddress'),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [{ chain: 'xdc', networks: ['xinfin', 'apothem'] }],
  };
}
