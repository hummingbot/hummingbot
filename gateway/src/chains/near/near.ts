import { Account, Contract } from 'near-api-js';
import abi from './near.abi.json';
import { logger } from '../../services/logger';
import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { NearBase } from './near.base';
import { ContractMethods } from 'near-api-js/lib/contract';
import { getNearConfig } from './near.config';

export class Near extends NearBase {
  private static _instances: { [name: string]: Near };
  private _gasPrice: number;
  private _gasPriceRefreshInterval: number | null;
  private _nativeTokenSymbol: string;
  private _chain: string;

  private constructor(network: string) {
    const config = getNearConfig('near', network);
    super(
      'near',
      config.network.nodeURL,
      network,
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice,
      config.gasLimitTransaction,
      ConfigManagerV2.getInstance().get('database.transactionDbPath')
    );
    this._chain = config.network.name;
    this._nativeTokenSymbol = config.nativeCurrencySymbol;
    this._gasPrice = config.manualGasPrice;
    this._gasPriceRefreshInterval =
      config.network.gasPriceRefreshInterval !== undefined
        ? config.network.gasPriceRefreshInterval
        : null;

    this.updateGasPrice();
  }

  public static getInstance(network: string): Near {
    if (Near._instances === undefined) {
      Near._instances = {};
    }
    if (!(network in Near._instances)) {
      Near._instances[network] = new Near(network);
    }

    return Near._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Near } {
    return Near._instances;
  }

  public get gasPrice(): number {
    return this._gasPrice;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public get chain(): string {
    return this._chain;
  }

  getContract(tokenAddress: string, account: Account) {
    return new Contract(account, tokenAddress, <ContractMethods>abi);
  }

  getSpender(reqSpender: string): string {
    return reqSpender;
  }

  /**
   * Automatically update the prevailing gas price on the network.
   */
  async updateGasPrice(): Promise<void> {
    if (this._gasPriceRefreshInterval === null) {
      return;
    }

    const gasPrice = await this.getGasPrice();
    if (gasPrice !== null) {
      this._gasPrice = Number(gasPrice);
    } else {
      logger.info('gasPrice is unexpectedly null.');
    }

    setTimeout(
      this.updateGasPrice.bind(this),
      this._gasPriceRefreshInterval * 1000
    );
  }

  // cancel transaction
  async cancelTx(account: Account, nonce: number): Promise<string> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    return super.cancelTx(account, nonce);
  }
}
