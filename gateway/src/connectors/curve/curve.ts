import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { Wallet } from 'ethers';
import { getEthereumConfig } from '../../chains/ethereum/ethereum.config';
// import {curve as _curve} from '@curvefi/api/lib/curve'

// curve is exposed as a singleton so we can only have one instance of curve
// with a set of values at a time.
import curve from '@curvefi/api';

export class Curve {
  public readonly types: string = 'Curve';
  private static _instances: { [name: string]: Curve };
  private _chain: string;
  private _chainId;
  private _ethereum: Ethereum;
  private _network: string;
  private _gasLimit: number;

  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    this._ethereum = Ethereum.getInstance(network);
    this._chain = chain;
    this._chainId = this._ethereum.chainId;
    this._network = network;
    this._gasLimit = 200000;
  }

  public static getInstance(chain: string, network: string): Curve {
    if (Curve._instances === undefined) {
      Curve._instances = {};
    }
    if (!(chain + network in Curve._instances)) {
      Curve._instances[chain + network] = new Curve(chain, network);
    }

    return Curve._instances[chain + network];
  }

  // // 1. Dev
  // await curve.init('JsonRpc', {url: 'http://localhost:8545/', privateKey: ''}, { gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0, chainId: 1 });
  // // OR
  // await curve.init('JsonRpc', {}, { chainId: 1 }); // In this case fee data will be specified automatically

  // // 2. Infura
  // curve.init("Infura", { network: "homestead", apiKey: <INFURA_KEY> }, { chainId: 1 });

  // // 3. Web3 provider
  // curve.init('Web3', { externalProvider: <WEB3_PROVIDER> }, { chainId: 1 });

  public async init() {
    if (this._chain == 'ethereum' && !this._ethereum.ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );

    await curve.init(
      'Infura',
      {
        network: this._network,
        apiKey: getEthereumConfig(this._chain, this._network).nodeAPIKey,
      },
      { chainId: this._chainId }
    );

    this._ready = true;
  }

  async initCurve(wallet: Wallet): Promise<void> {
    const config = getEthereumConfig('ethereum', this._network);
    await curve.init(
      'JsonRpc',
      {
        url: config.network.nodeURL + config.nodeAPIKey,
        privateKey: wallet.privateKey,
      },
      { chainId: this._chainId }
    );
  }

  public get ready(): boolean {
    return this._ready;
  }

  public get gasLimit(): number {
    return this._gasLimit;
  }

  async price(
    tokenIn: string,
    tokenOut: string,
    tokenAmount: string
  ): Promise<any> {
    // await this.initCurve(wallet);
    const { route, output } = await curve.getBestRouteAndOutput(
      tokenIn,
      tokenOut,
      tokenAmount
    );
    return { route, output };
  }

  // maxSlippage
  async executeTrade(
    tokenIn: string,
    tokenOut: string,
    tokenAmount: string
  ): Promise<any> {
    // await this.initCurve(wallet);
    await curve.routerExchange(tokenIn, tokenOut, tokenAmount); // returns transaction hash
  }

  // export interface TradeResponse {
  //   network: string;
  //   timestamp: number;
  //   latency: number;
  //   base: string;
  //   quote: string;
  //   amount: string;
  //   expectedIn?: string;
  //   expectedOut?: string;
  //   price: string;
  //   gasPrice: number;
  //   gasLimit: number;
  //   gasCost: string;
  //   nonce: number;
  //   txHash: string | undefined;
  // }
  // curve.estimateGas.getBestRouteAndOutput(tokenIn, tokenOut, tokenAmount);
}

// routerExchange
