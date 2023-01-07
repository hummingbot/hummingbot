import { Network } from '@injectivelabs/networks';
import { ChainId } from '@injectivelabs/ts-types';

export function getChainIdFromString(chainId: string): ChainId | null {
  if (chainId === 'mainnet') {
    return ChainId.Mainnet;
  } else if (chainId === 'testnet') {
    return ChainId.Testnet;
  } else if (chainId === 'devnet') {
    return ChainId.Devnet;
  } else {
    return null;
  }
}

export function chainIdToInt(chainId: ChainId): number {
  if (chainId === ChainId.Mainnet) {
    return 1;
  } else if (chainId === ChainId.Testnet) {
    return 2;
  } else if (chainId === ChainId.Devnet) {
    return 3;
  } else {
    throw `Unrecognized chain ID ${chainId}.`;
  }
}

export function getNetworkFromString(network: string): Network | null {
  if (network === 'mainnetK8s') {
    return Network.MainnetK8s;
  } else if (network === 'mainnet') {
    return Network.Mainnet;
  } else if (network === 'staging') {
    return Network.Staging;
  } else if (network === 'public') {
    return Network.Public;
  } else if (network === 'testnetK8s') {
    return Network.TestnetK8s;
  } else if (network === 'testnet') {
    return Network.Testnet;
  } else if (network === 'devnet1') {
    return Network.Devnet1;
  } else if (network === 'devnet') {
    return Network.Devnet;
  } else if (network === 'local') {
    return Network.Local;
  } else {
    return null;
  }
}

export function networkToString(network: Network): string {
  if (network === Network.MainnetK8s) {
    return 'mainnetK8s';
  } else if (network === Network.Mainnet) {
    return 'mainnet';
  } else if (network === Network.Staging) {
    return 'staging';
  } else if (network === Network.Public) {
    return 'public';
  } else if (network === Network.TestnetK8s) {
    return 'testnetK8s';
  } else if (network === Network.Testnet) {
    return 'testnet';
  } else if (network === Network.Devnet1) {
    return 'devnet1';
  } else if (network === Network.Devnet) {
    return 'devnet';
  } else if (network === Network.Local) {
    return 'local';
  } else {
    throw `Unrecognized network ${network}.`;
  }
}
