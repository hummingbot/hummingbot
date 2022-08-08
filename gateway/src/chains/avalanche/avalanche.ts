import abi from '../../services/ethereum.abi.json';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { getEthereumConfig as getAvalancheConfig } from '../ethereum/ethereum.config';
import { Provider } from '@ethersproject/abstract-provider';
import { TraderjoeConfig } from '../../connectors/traderjoe/traderjoe.config';
import { PangolinConfig } from '../../connectors/pangolin/pangolin.config';
import { OpenoceanConfig } from '../../connectors/openocean/openocean.config';
import { Ethereumish } from '../../services/common-interfaces';
import { ConfigManagerV2 } from '../../services/config-manager-v2';

export class Avalanche extends EthereumBase implements Ethereumish {
  private static _instances: { [name: string]: Avalanche };
  private _gasPrice: number;
  private _gasPriceRefreshInterval: number | null;
  private _nativeTokenSymbol: string;
  private _chain: string;

  private constructor(network: string) {
    const config = getAvalancheConfig('avalanche', network);
    super(
      'avalanche',
      config.network.chainID,
      config.network.nodeURL,
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice,
      config.gasLimitTransaction,
      ConfigManagerV2.getInstance().get('database.nonceDbPath'),
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

  public static getInstance(network: string): Avalanche {
    if (Avalanche._instances === undefined) {
      Avalanche._instances = {};
    }
    if (!(network in Avalanche._instances)) {
      Avalanche._instances[network] = new Avalanche(network);
    }

    return Avalanche._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Avalanche } {
    return Avalanche._instances;
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

  getContract(tokenAddress: string, signerOrProvider?: Wallet | Provider) {
    return new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    let spender: string;
    if (reqSpender === 'pangolin') {
      spender = PangolinConfig.config.routerAddress(this._chain);
    } else if (reqSpender === 'openocean') {
      spender = OpenoceanConfig.config.routerAddress(this._chain);
    } else if (reqSpender === 'traderjoe') {
      spender = TraderjoeConfig.config.routerAddress(this._chain);
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
    return super.cancelTxWithGasPrice(wallet, nonce, this._gasPrice * 2);
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
      this._gasPrice = gasPrice;
    } else {
      logger.info('gasPrice is unexpectedly null.');
    }

    setTimeout(
      this.updateGasPrice.bind(this),
      this._gasPriceRefreshInterval * 1000
    );
  }

  async close() {
    await super.close();
    if (this._chain in Avalanche._instances) {
      delete Avalanche._instances[this._chain];
    }
  }
}
