import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { Transaction, Wallet } from 'ethers';
import BigNumber from 'bignumber.js';
import { getEthereumConfig } from '../../chains/ethereum/ethereum.config';
import { TokenInfo } from '../../services/ethereum-base';

// curve is exposed as a singleton so we can only have one instance of curve
// with a set of values at a time.
import curve from '@curvefi/api';

export interface ExpectedTrade {
  route: any;
  outputAmount: string;
  expectedAmount: string;
}

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

  public async init() {
    await this._ethereum.init();
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

    // await curve.init(
    //   'JsonRpc',
    //   {
    //     url:
    //       getEthereumConfig(this._chain, this._network).network.nodeURL +
    //       getEthereumConfig(this._chain, this._network).nodeAPIKey,
    //     // privateKey: wallet.privateKey,
    //   },
    //   { chainId: this._chainId }
    // );

    this._ready = true;
  }

  async prepWallet(wallet: Wallet): Promise<void> {
    await curve.init(
      'JsonRpc',
      {
        url:
          getEthereumConfig(this._chain, this._network).network.nodeURL +
          getEthereumConfig(this._chain, this._network).nodeAPIKey,
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

  async estimateTrade(
    baseToken: TokenInfo,
    quoteToken: TokenInfo,
    tokenAmount: string,
    side: string
  ): Promise<ExpectedTrade> {
    let route;
    let outputAmount;
    let expectedAmount;

    if (side === 'BUY') {
      const best = await curve.getBestRouteAndOutput(
        baseToken.address,
        quoteToken.address,
        tokenAmount
      );
      route = best.route;
      outputAmount = best.output;
      expectedAmount = await curve.routerExchangeExpected(
        baseToken.address,
        quoteToken.address,
        tokenAmount
      );
    } else {
      const best = await curve.getBestRouteAndOutput(
        quoteToken.address,
        baseToken.address,
        tokenAmount
      );
      route = best.route;
      outputAmount = best.output;
      expectedAmount = await curve.routerExchangeExpected(
        quoteToken.address,
        baseToken.address,
        tokenAmount
      );
    }

    return {
      route,
      outputAmount,
      expectedAmount,
    };
  }

  async executeTrade(
    wallet: Wallet,
    gasPrice: number,
    baseToken: TokenInfo,
    quoteToken: TokenInfo,
    tokenAmount: string,
    side: string,
    nonce: number,
    maxFeePerGas?: number,
    maxPriorityFeePerGas?: BigNumber
    // allowedSlippage?: string
  ): Promise<Transaction> {
    await this.prepWallet(wallet);

    if (side === 'BUY') {
      if (maxFeePerGas !== undefined || maxPriorityFeePerGas !== undefined) {
        return await curve.routerExchange(
          baseToken.address,
          quoteToken.address,
          tokenAmount,
          nonce,
          new BigNumber(this.gasLimit),
          new BigNumber(gasPrice),
          maxFeePerGas
          //          maxPriorityFeePerGas
        );
      } else {
        return await curve.routerExchange(
          quoteToken.address,
          baseToken.address,
          tokenAmount,
          nonce,
          new BigNumber(this.gasLimit),
          new BigNumber(gasPrice)
          // maxFeePerGas,
          // maxPriorityFeePerGas
        );
      }
    } else {
      return await curve.routerExchange(
        quoteToken.address,
        baseToken.address,
        tokenAmount,
        nonce,
        new BigNumber(this.gasLimit),
        new BigNumber(gasPrice)
      );
    }
  }
}
