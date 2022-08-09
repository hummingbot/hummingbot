/* WIP */
import { Cosmosish } from '../../services/common-interfaces';
import { CosmosBase } from '../../services/cosmos-base';
import { getSifchainConfig } from './sifchain.config';
import { logger } from '../../services/logger';
const { SifSigningStargateClient } = require('@sifchain/stargate');

export class Sifchain extends CosmosBase implements Cosmosish {
  private static _instances: { [name: string]: Sifchain };
  private _gasPrice: number;
  private _gasPriceLastUpdated: Date | null;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _requestCount: number;
  private _metricsLogInterval: number;
  private _signingClient;

  private constructor(network: string) {
    const config = getSifchainConfig('sifchain', network);
    super(
      'sifchain',
      config.network.rpcURL,
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice
    );
    this._chain = network;
    this._signingClient = SifSigningStargateClient.connect(
      config.network.rpcURL
    );
    this._nativeTokenSymbol = config.nativeCurrencySymbol;
    this._gasPrice = config.manualGasPrice;
    this._gasPriceLastUpdated = null;

    // this.updateGasPrice();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    // this.onDebugMessage(this.requestCounter.bind(this));
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

  public get signingClient() {
    return this._signingClient;
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
