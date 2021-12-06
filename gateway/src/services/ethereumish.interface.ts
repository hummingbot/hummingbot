import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from './ethereum-base';
import { Provider } from '@ethersproject/abstract-provider';

export interface Ethereumish extends EthereumBase {
  cancelTx(wallet: Wallet, nonce: number): Promise<Transaction>;
  getSpender(reqSpender: string): string;
  getContract(
    tokenAddress: string,
    signerOrProvider?: Wallet | Provider
  ): Contract;
  gasPrice: number;
  nativeTokenSymbol: string;
  chain: string;
}
