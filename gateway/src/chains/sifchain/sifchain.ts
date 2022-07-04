import abi from '../../services/ethereum.abi.json';
import axios, { AxiosRequestConfig } from 'axios';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { getSifchainConfig } from './sifchain.config';
import { Provider } from '@ethersproject/abstract-provider';
// import { SushiSwapConfig } from './sushiswap/sushiswap.config';

export class Sifchain {
  private static _instances: { [name: string]: Sifchain };
  private _gasPrice: number;
  private _gasPriceLastUpdated: Date | null;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _requestCount: number;
  private _metricsLogInterval: number;

  private constructor(network: string) {
    const config = getSifchainConfig('sifchain', network);
    this._chain = network;
    this._nativeTokenSymbol = config.nativeCurrencySymbol;
    this._gasPrice = config.manualGasPrice;
    this._gasPriceLastUpdated = null;

    this.updateGasPrice();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public static getInstance(network: string): Sifchain {
    if (Sifchain._instances === undefined) {
      Sifchain._instances = {};
    }
    if (!(network in Sifchain._instances)) {
      Sifchain._instances[network] = new Sifchain(network);
    }

    return Sifchain._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Sifchain } {
    return Sifchain._instances;
  }

  // public static reload(): Sifchain {
  //   Sifchain._instance = new Sifchain();
  //   return Sifchain._instance;
  // }

  public requestCounter(msg: any): void {
    if (msg.action === 'request') this._requestCount += 1;
  }

  public metricLogger(): void {
    logger.info(
      this.requestCount +
        ' request(s) sent in last ' +
        this.metricsLogInterval / 1000 +
        ' seconds.'
    );
    this._requestCount = 0; // reset
  }

  // getters
  public get gasPrice(): number {
    return this._gasPrice;
  }

  public get chain(): string {
    return this._chain;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public get gasPriceLastDated(): Date | null {
    return this._gasPriceLastUpdated;
  }

  public get requestCount(): number {
    return this._requestCount;
  }

  public get metricsLogInterval(): number {
    return this._metricsLogInterval;
  }

  async updateGasPrice(): Promise<void> {
    const SifchainConfig = getSifchainConfig('sifchain', this._chain);

    if (SifchainConfig.autoGasPrice) {
      const jsonData = JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'hmyv2_gasPrice',
        params: [],
      });

      const config: AxiosRequestConfig = {
        method: 'post',
        url: SifchainConfig.network.nodeURL,
        headers: {
          'Content-Type': 'application/json',
        },
        data: jsonData,
      };

      const { data } = await axios(config);

      // divide by 10 to convert it to Gwei
      this._gasPrice = data['result'] / 10;
      this._gasPriceLastUpdated = new Date();

      setTimeout(
        this.updateGasPrice.bind(this),
        SifchainConfig.gasPricerefreshTime * 1000
      );
    }
  }

  getContract(tokenAddress: string, signerOrProvider?: Wallet | Provider) {
    return new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    // TODO: Add SifDex
    let spender: string;
    if (reqSpender === 'sushiswap') {
      spender = '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506';
    }
    if (reqSpender === 'viperswap') {
      spender = '0xf012702a5f0e54015362cbca26a26fc90aa832a3';
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
