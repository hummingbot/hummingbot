import abi from '../../services/ethereum.abi.json';
import axios, { AxiosRequestConfig } from 'axios';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { getHarmonyConfig } from './harmony.config';
import { Provider } from '@ethersproject/abstract-provider';
import { Ethereumish } from '../../services/common-interfaces';
import { ConfigManagerV2 } from '../../services/config-manager-v2';

export class Harmony extends EthereumBase implements Ethereumish {
  private static _instances: { [name: string]: Harmony };
  private _gasPrice: number;
  private _gasPriceLastUpdated: Date | null;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _requestCount: number;
  private _metricsLogInterval: number;

  private constructor(network: string) {
    const config = getHarmonyConfig('harmony', network);
    super(
      'harmony',
      config.network.chainID,
      config.network.nodeURL,
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice,
      config.gasLimitTransaction,
      ConfigManagerV2.getInstance().get('database.nonceDbPath'),
      ConfigManagerV2.getInstance().get('database.transactionDbPath')
    );
    this._chain = network;
    this._nativeTokenSymbol = config.nativeCurrencySymbol;
    this._gasPrice = config.manualGasPrice;
    this._gasPriceLastUpdated = null;

    this.updateGasPrice();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    this.onDebugMessage(this.requestCounter.bind(this));
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public static getInstance(network: string): Harmony {
    if (Harmony._instances === undefined) {
      Harmony._instances = {};
    }
    if (!(network in Harmony._instances)) {
      Harmony._instances[network] = new Harmony(network);
    }

    return Harmony._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Harmony } {
    return Harmony._instances;
  }

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
    const harmonyConfig = getHarmonyConfig('harmony', this._chain);

    if (harmonyConfig.autoGasPrice) {
      const jsonData = JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'hmyv2_gasPrice',
        params: [],
      });

      const config: AxiosRequestConfig = {
        method: 'post',
        url: harmonyConfig.network.nodeURL,
        headers: {
          'Content-Type': 'application/json',
        },
        data: jsonData,
      };

      const { data } = await axios(config);

      // divide by 1e9 to convert it to Gwei
      this._gasPrice = data['result'] / 1e9;
      this._gasPriceLastUpdated = new Date();

      setTimeout(
        this.updateGasPrice.bind(this),
        harmonyConfig.gasPricerefreshTime * 1000
      );
    }
  }

  getContract(tokenAddress: string, signerOrProvider?: Wallet | Provider) {
    return new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    // TODO: add SushiswapConfig and ViperswapConfig and Defira configs (or move `approve` to AMM)
    let spender: string;
    if (reqSpender === 'sushiswap') {
      spender = '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506';
    } else if (reqSpender === 'viperswap') {
      spender = '0xf012702a5f0e54015362cbca26a26fc90aa832a3';
    } else if (reqSpender === 'defikingdoms') {
      spender = '0x24ad62502d1C652Cc7684081169D04896aC20f30';
    } else if (reqSpender === 'defira') {
      spender = '0x3C8BF7e25EbfAaFb863256A4380A8a93490d8065';
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
    return this.cancelTxWithGasPrice(wallet, nonce, this._gasPrice * 2);
  }

  async close() {
    await super.close();
    if (this._chain in Harmony._instances) {
      delete Harmony._instances[this._chain];
    }
  }
}
