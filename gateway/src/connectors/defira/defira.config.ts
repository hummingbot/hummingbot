import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace DefiraConfig {
  export interface NetworkConfig {
    allowedSlippage: () => string;
    gasLimitEstimate: () => number;
    ttl: () => number;
    routerAddress: (network: string) => string;
    initCodeHash: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: () =>
      ConfigManagerV2.getInstance().get(`defira.allowedSlippage`),
    gasLimitEstimate: () =>
      ConfigManagerV2.getInstance().get(`defira.gasLimitEstimate`),
    ttl: () => ConfigManagerV2.getInstance().get(`defira.ttl`),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `defira.contractAddresses.${network}.routerAddress`
      ),
    initCodeHash: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `defira.contractAddresses.${network}.initCodeHash`
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      {
        chain: 'harmony',
        networks: ['mainnet', 'testnet'],
      },
    ],
  };
}
