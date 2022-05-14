import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace DefiraConfig {
  export interface NetworkConfig {
    allowedSlippage: () => string;
    gasLimit: () => number;
    ttl: () => number;
    uniswapV2RouterAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: () =>
      ConfigManagerV2.getInstance().get(`defira.versions.v2.allowedSlippage`),
    gasLimit: () => ConfigManagerV2.getInstance().get(`defira.gasLimit`),
    ttl: () => ConfigManagerV2.getInstance().get(`defira.ttl`),
    uniswapV2RouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `defira.contractAddresses.${network}.routerAddress`
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
