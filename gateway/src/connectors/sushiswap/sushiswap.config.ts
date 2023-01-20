import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace SushiswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimitEstimate: number;
    ttl: number;
    sushiswapRouterAddress: (chain: string, network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'sushiswap.allowedSlippage'
    ),
    gasLimitEstimate: ConfigManagerV2.getInstance().get(
      'sushiswap.gasLimitEstimate'
    ),
    ttl: ConfigManagerV2.getInstance().get('sushiswap.ttl'),
    sushiswapRouterAddress: (chain: string, network: string) =>
      ConfigManagerV2.getInstance().get(
        'sushiswap.contractAddresses.' +
          chain +
          '.' +
          network +
          '.sushiswapRouterAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: ['mainnet', 'kovan', 'goerli', 'ropsten'],
      },
      { chain: 'binance-smart-chain', networks: ['mainnet', 'testnet'] },
    ],
  };
}
