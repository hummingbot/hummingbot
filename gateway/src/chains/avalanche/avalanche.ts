import abi from '../../services/ethereum.abi.json';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { ConfigManager } from '../../services/config-manager';
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
    let config;
    switch (ConfigManager.config.AVALANCHE_CHAIN) {
      case 'fuji':
        config = AvalancheConfig.config.fuji;
        break;
      case 'avalanche':
        config = AvalancheConfig.config.avalanche;
        break;
      default:
        throw new Error('AVALANCHE_CHAIN not valid');
    }

    super(
      'avalanche',
      config.chainId,
      config.rpcUrl,
      config.tokenListSource,
      config.tokenListType,
      ConfigManager.config.AVAX_MANUAL_GAS_PRICE
    );
    this._chain = ConfigManager.config.AVALANCHE_CHAIN;
    this._nativeTokenSymbol = 'AVAX';
    this._gasPrice = ConfigManager.config.AVAX_MANUAL_GAS_PRICE;
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
      if (ConfigManager.config.ETHEREUM_CHAIN === 'avalanche') {
        spender = PangolinConfig.config.avalanche.routerAddress;
      } else {
        spender = PangolinConfig.config.fuji.routerAddress;
      }
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
