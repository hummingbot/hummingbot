import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { xrpToDrops } from 'xrpl'
import { BigNumber } from "bignumber.js";

export interface NetworkConfig {
  name: string;
  nodeUrl: string;
  // "XRP"
  nativeCurrencySymbol: string;
  // custom list of tokens to trade
  trustlines: string[] | undefined;
}

export interface Config {
  // "mainnet" | "testnet" | "devnet"
  network: NetworkConfig;
  // 10
  minimumFee: number;
  // 1e-6
  dropsToXRP: number;
  timeToLive: number;
  customNodeUrl: string | undefined;
}

// @todo: find out which configs are required
export function getRippleConfig(
  chainName: string,
  networkName: string
): Config {
  const configManager = ConfigManagerV2.getInstance();
  return {
    network: {
      name: networkName,
      nodeUrl: configManager.get(
        chainName + '.networks.' + networkName + '.nodeURL'
      ),
      nativeCurrencySymbol: configManager.get(
        chainName + '.networks.' + networkName + '.nativeCurrencySymbol'
      ),
      trustlines: configManager.get(
        chainName + '.networks.' + networkName + '.trustlines'
      ),
    },
    minimumFee: configManager.get(chainName + '.minimumFee'),
    dropsToXRP: 1 / Number.parseFloat(xrpToDrops(new BigNumber(1))),
    timeToLive: configManager.get(chainName + '.timeToLive'),
    customNodeUrl: configManager.get(chainName + '.customNodeUrl'),
  };
}
