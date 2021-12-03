import abi from '../../services/ethereum.abi.json';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { AvalancheConfig } from './avalanche.config';
import { Provider } from '@ethersproject/abstract-provider';
import { PangolinConfig } from './pangolin/pangolin.config';
import { Ethereumish } from '../../services/ethereumish.interface';
export class Avalanche extends EthereumBase implements Ethereumish {
  private static _instance: Avalanche;
  private _gasPrice: number;
  private _nativeTokenSymbol: string;
  private _chain: string;

  private constructor() {
    const config = AvalancheConfig.config.network;

    super(
      'avalanche',
      config.chainID,
      config.nodeURL,
      config.tokenListSource,
      config.tokenListType,
      AvalancheConfig.config.manualGasPrice
    );
    this._chain = AvalancheConfig.config.network.name;
    this._nativeTokenSymbol = AvalancheConfig.config.nativeCurrencySymbol;
    this._gasPrice = AvalancheConfig.config.manualGasPrice;
  }

  public static getInstance(): Avalanche {
    if (!Avalanche._instance) {
      Avalanche._instance = new Avalanche();
    }

    return Avalanche._instance;
  }

  // getters

  public get gasPrice(): number {
    return this._gasPrice;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public get chain(): string {
    return this._chain;
  }

  // public get gasPriceLastDated(): Date | null {
  //   return this._gasPriceLastUpdated;
  // }

  getContract(tokenAddress: string, signerOrProvider?: Wallet | Provider) {
    return new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    let spender: string;
    if (reqSpender === 'pangolin') {
      spender = PangolinConfig.config.routerAddress;
    } else {
      spender = reqSpender;
    }
    return spender;
  }

  // cancel transaction
  async cancelTx(wallet: Wallet, nonce: number): Promise<Transaction> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    return super.cancelTx(wallet, nonce, this._gasPrice);
  }
}
