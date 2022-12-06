import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export interface Amms {
  [key: string]: string;
}

export namespace PalmConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    ttl: number;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
    amms: (network: string) => Amms;
    clearingHouse: (network: string) => string;
    clearingHouseViewer: (network: string) => string;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      `palmswap.allowedSlippage`
    ),
    ttl: ConfigManagerV2.getInstance().get(`palmswap.versions.ttl`),
    tradingTypes: ['EVM_Perpetual'],
    availableNetworks: [
      { chain: 'binance-smart-chain', networks: ['mainnet', 'testnet'] },
    ],
    amms: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `palmswap.contractAddresses.${network}.amms`
      ),
    clearingHouse: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `palmswap.contractAddresses.${network}.clearingHouse`
      ),
    clearingHouseViewer: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `palmswap.contractAddresses.${network}.clearingHouseViewer`
      ),
  };
}
