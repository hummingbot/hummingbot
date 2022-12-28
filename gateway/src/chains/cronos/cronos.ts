import abi from '../../services/ethereum.abi.json';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { getEthereumConfig as getCronosConfig } from '../ethereum/ethereum.config';
import { Provider } from '@ethersproject/abstract-provider';
import { Ethereumish } from '../../services/common-interfaces';
import { MadMeerkatConfig } from '../../connectors/mad_meerkat/mad_meerkat.config';
import { VVSConfig } from '../../connectors/vvs/vvs.config';
import { ConfigManagerV2 } from '../../services/config-manager-v2';

export class Cronos extends EthereumBase implements Ethereumish {
  private static _instances: { [name: string]: Cronos };
  private _gasPrice: number;
  private _gasPriceRefreshInterval: number | null;
  private _nativeTokenSymbol: string;
  private _chain: string;

  private constructor(network: string) {
    const config = getCronosConfig('cronos', network);
    super(
      'cronos',
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

  public static getInstance(network: string): Cronos {
    if (Cronos._instances === undefined) {
      Cronos._instances = {};
    }
    if (!(network in Cronos._instances)) {
      Cronos._instances[network] = new Cronos(network);
    }

    return Cronos._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Cronos } {
    return Cronos._instances;
  }

  /**
   * Automatically update the prevailing gas price on the network from the connected RPC node.
   */
  async updateGasPrice(): Promise<void> {
    if (this._gasPriceRefreshInterval === null) {
      return;
    }

    const gasPrice: number = (await this.provider.getGasPrice()).toNumber();

    this._gasPrice = gasPrice * 1e-9;

    setTimeout(
      this.updateGasPrice.bind(this),
      this._gasPriceRefreshInterval * 1000
    );
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
    if (reqSpender === 'mad_meerkat') {
      spender = MadMeerkatConfig.config.routerAddress(this._chain);
    } else if (reqSpender == 'vvs') {
      spender = VVSConfig.config.routerAddress(this._chain);
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
}
