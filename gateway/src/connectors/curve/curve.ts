import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { isFractionString } from '../../services/validators';
import { percentRegexp } from '../../services/config-manager-v2';
import { Transaction, Wallet } from 'ethers';
import BigNumber from 'bignumber.js';
import { getEthereumConfig } from '../../chains/ethereum/ethereum.config';
import { TokenInfo } from '../../services/ethereum-base';
import { CurveConfig } from './curve.config';

// curve is exposed as a singleton so we can only have one instance of curve
// with a set of values at a time.
import curve from '@curvefi/api';

export interface ExpectedTrade {
  route: any;
  outputAmount: string;
  expectedAmount: string;
}

// track previous curve init params. If they differ from the current ones,
// reinit curve. This is necessary because the curve object from curve-js is a
// global singleton
export interface PreviousCurveInitParams {
  wallet: Wallet;
  gasPrice?: number;
  maxFeePerGas?: BigNumber;
  maxPriorityFeePerGas?: BigNumber;
}

export class Curve {
  public readonly types: string = 'Curve';
  private static _instances: { [name: string]: Curve };
  private _chain: string;
  private _chainId;
  private _ethereum: Ethereum;
  private _network: string;
  private _gasLimit: number;
  private _previousCurveInitParams: PreviousCurveInitParams | null = null;

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
        network: getEthereumConfig(this._chain, this._network).network.nodeURL,
        apiKey: getEthereumConfig(this._chain, this._network).nodeAPIKey,
      },
      { chainId: this._chainId }
    );

    this._ready = true;
  }

  async prepWallet(
    wallet: Wallet,
    gasPrice?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<void> {
    if (
      this._previousCurveInitParams !==
      { wallet, gasPrice, maxFeePerGas, maxPriorityFeePerGas }
    ) {
      let options: Record<string, any> = {};
      if (gasPrice !== null) options['gasPrice'] = gasPrice;
      if (maxFeePerGas !== null) options['maxFeePerGas'] = maxFeePerGas;
      if (maxPriorityFeePerGas !== null)
        options['maxPriorityFeePerGas'] = maxPriorityFeePerGas;

      await curve.init(
        'Infura',
        {
          network: getEthereumConfig(this._chain, this._network).network
            .nodeURL,
          apiKey: getEthereumConfig(this._chain, this._network).nodeAPIKey,
          privateKey_: wallet.privateKey,
        },
        { ...options, chainId: this._chainId }
      );

      this._previousCurveInitParams = {
        wallet,
        gasPrice,
        maxFeePerGas,
        maxPriorityFeePerGas,
      };
    }
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

  /**
   * Gets the allowed slippage percent from the optional parameter or the value
   * in the configuration.
   *
   * @param allowedSlippageStr (Optional) should be of the form '1/10'.
   */
  public getAllowedSlippage(allowedSlippageStr?: string): number | undefined {
    if (allowedSlippageStr != null && isFractionString(allowedSlippageStr)) {
      const fractionSplit = allowedSlippageStr.split('/');
      return parseInt(fractionSplit[0]) / parseInt(fractionSplit[1]);
    }

    const allowedSlippage = CurveConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return parseInt(nd[1]) / parseInt(nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  /**
   * Execute a curve trade on the blockchain.
   *
   * @param wallet Wallet
   * @param gasPrice Base gas price, for pre-EIP1559 transactions
   * @param baseToken
   * @param quoteToken
   * @param tokenAmount
   * @param side
   * @param gasLimit Gas limit
   * @param nonce (Optional) EVM transaction nonce
   * @param maxFeePerGas (Optional) Maximum total fee per gas you want to pay
   * @param maxPriorityFeePerGas (Optional) Maximum tip per gas you want to pay
   */
  async executeTrade(
    wallet: Wallet,
    gasPrice: number,
    baseToken: TokenInfo,
    quoteToken: TokenInfo,
    tokenAmount: string,
    side: string,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber,
    allowedSlippage?: string
  ): Promise<Transaction> {
    await this.prepWallet(wallet, gasPrice, maxFeePerGas, maxPriorityFeePerGas);

    if (nonce === undefined) {
      nonce = await this._ethereum.nonceManager.getNonce(wallet.address);
    }

    if (side === 'BUY') {
      return await curve.routerExchange(
        baseToken.address,
        quoteToken.address,
        tokenAmount,
        nonce,
        gasLimit,
        this.getAllowedSlippage(allowedSlippage)
      );
    } else {
      return await curve.routerExchange(
        quoteToken.address,
        baseToken.address,
        tokenAmount,
        nonce,
        gasLimit,
        this.getAllowedSlippage(allowedSlippage)
      );
    }
  }
}
