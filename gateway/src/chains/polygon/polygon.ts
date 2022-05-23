import abi from '../../services/ethereum.abi.json';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { getEthereumConfig as getPolygonConfig } from '../ethereum/ethereum.config';
import { Provider } from '@ethersproject/abstract-provider';
import { Ethereumish } from '../../services/common-interfaces';
import { replaceOrAppend } from '../../services/base';

export class Polygon extends EthereumBase implements Ethereumish {
  private static _instances: { [name: string]: Polygon };
  private _gasPrice: number;
  private _nativeTokenSymbol: string;
  private _chain: string;

  private constructor(network: string) {
    const config = getPolygonConfig('polygon', network);
    super(
      'polygon',
      config.network.chainID,
      replaceOrAppend(config.network.nodeURL, config.nodeAPIKey),
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice,
      config.gasLimit
    );
    this._chain = config.network.name;
    this._nativeTokenSymbol = config.nativeCurrencySymbol;
    this._gasPrice = config.manualGasPrice;
  }

  public static getInstance(network: string): Polygon {
    if (Polygon._instances === undefined) {
      Polygon._instances = {};
    }
    if (!(network in Polygon._instances)) {
      Polygon._instances[network] = new Polygon(network);
    }

    return Polygon._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Polygon } {
    return Polygon._instances;
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

  getContract(tokenAddress: string, signerOrProvider?: Wallet | Provider) {
    return new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    // TODO: update this after implementing a connector for Polygon
    // let spender: string;
    // if (reqSpender === 'pangolin') {
    //   spender = PangolinConfig.config.routerAddress(this._chain);
    // } else {
    //   spender = reqSpender;
    // }
    // return spender;
    return reqSpender;
  }

  // cancel transaction
  async cancelTx(wallet: Wallet, nonce: number): Promise<Transaction> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    return super.cancelTxWithGasPrice(wallet, nonce, this._gasPrice * 2);
  }
}
