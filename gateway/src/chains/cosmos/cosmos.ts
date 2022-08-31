import { Cosmosish } from '../../services/common-interfaces';
import { CosmosBase } from '../../services/cosmos-base';
import { getCosmosConfig } from './cosmos.config';
import { logger } from '../../services/logger';

export class Cosmos extends CosmosBase implements Cosmosish {
  private static _instances: { [name: string]: Cosmos };
  private _gasPrice: number;
  private _gasPriceLastUpdated: Date | null;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _requestCount: number;
  private _metricsLogInterval: number;

  private constructor(network: string) {
    const config = getCosmosConfig('cosmos');
    super(
      'cosmos',
      config.network.rpcURL,
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice
    );
    this._chain = network;
    this._nativeTokenSymbol = config.nativeCurrencySymbol;

    this._gasPrice = config.manualGasPrice;
    this._gasPriceLastUpdated = null;

    // this.updateGasPrice();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public static getInstance(network: string): Cosmos {
    if (Cosmos._instances === undefined) {
      Cosmos._instances = {};
    }
    if (!(network in Cosmos._instances)) {
      Cosmos._instances[network] = new Cosmos(network);
    }
    return Cosmos._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Cosmos } {
    return Cosmos._instances;
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
}
