import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace SushiswapConfig {
  export interface NetworkConfig {
    allowedSlippage: (version: number) => string;
    gasLimit: (version: number) => number;
    ttl: (version: number) => number;
    sushiswapRouterAddress: (network: string) => string;
    tradingTypes: (network: string) => Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: (version: number) =>
      ConfigManagerV2.getInstance().get(
        `sushiswap.versions.v${version}.allowedSlippage`
      ),
    gasLimit: (version: number) =>
      ConfigManagerV2.getInstance().get(
        `sushiswap.versions.v${version}.gasLimit`
      ),
    ttl: (version: number) =>
      ConfigManagerV2.getInstance().get(`sushiswap.versions.v${version}.ttl`),
      sushiswapRouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `sushiswap.contractAddresses.${network}.sushiswapRouterAddress`
      ),
    tradingTypes: (network: string) =>
      network === 'v2' ? ['EVM_AMM'] : ['EVM_Range_AMM'],
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('sushiswap.contractAddresses')
        ),
      },
    ],
  };
}
