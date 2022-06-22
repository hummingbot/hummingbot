import abi from '../../services/ethereum.abi.json';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { getEthereumConfig as getBscConfig } from '../ethereum/ethereum.config';
import { Provider } from '@ethersproject/abstract-provider';
import { Ethereumish } from '../../services/common-interfaces';
import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { replaceOrAppend } from '../../services/base';
import { PancakeswapConfig } from '../../connectors/pancakeswap/pancakeswap.config';

export class BSC extends EthereumBase implements Ethereumish {
  private static _instances: { [name: string]: BSC };
  private _gasPrice: number;
  private _nativeTokenSymbol: string;
  private _chain: string;

  private constructor(network: string) {
    const config = getBscConfig('bsc', network);
    super(
      'bsc',
      config.network.chainID,
      replaceOrAppend(config.network.nodeURL, config.nodeAPIKey),
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice,
      config.gasLimit,
      ConfigManagerV2.getInstance().get('database.nonceDbPath'),
      ConfigManagerV2.getInstance().get('database.transactionDbPath')
    );
    this._chain = config.network.name;
    this._nativeTokenSymbol = config.nativeCurrencySymbol;
    this._gasPrice = config.manualGasPrice;
  }

  public static getInstance(network: string): BSC {
    if (BSC._instances === undefined) {
      BSC._instances = {};
    }
    if (!(network in BSC._instances)) {
      BSC._instances[network] = new BSC(network);
    }

    return BSC._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: BSC } {
    return BSC._instances;
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
    if (reqSpender === 'pancakeswap') {
      spender = PancakeswapConfig.config.routerAddress(this._chain);
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

  async close() {
    await super.close();
    if (this._chain in BSC._instances) {
      delete BSC._instances[this._chain];
    }
  }
}
