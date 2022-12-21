import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace PancakeSwapConfig {
  export interface ExchangeConfig {
    allowedSlippage: string;
    gasLimitEstimate: number;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: ExchangeConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'pancakeswap.allowedSlippage'
    ),
    gasLimitEstimate: ConfigManagerV2.getInstance().get(
      `pancakeswap.gasLimitEstimate`
    ),
    ttl: ConfigManagerV2.getInstance().get('pancakeswap.ttl'),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'pancakeswap.contractAddresses.' + network + '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      { chain: 'binance-smart-chain', networks: ['mainnet', 'testnet'] },
    ],
  };
}
