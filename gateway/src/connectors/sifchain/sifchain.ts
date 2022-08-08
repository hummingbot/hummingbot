import { percentRegexp } from '../../services/config-manager-v2';
// import {
//   BigNumber,
//   Contract,
//   ContractInterface,
//   Transaction,
//   Wallet,
// } from 'ethers';

import { isFractionString } from '../../services/validators';
import { SifchainConnectorConfig } from './sifchain.config';
// import routerAbi from './IPangolinRouter.json';
import {
  Percent,
  // Router,
  Token,
  // TokenAmount,
  // Trade,
} from '@pangolindex/sdk';
const { Decimal } = require('@cosmjs/math');
// import { logger } from '../../services/logger';
import {
  ExpectedTrade,
  SifchainishConnector,
} from '../../services/common-interfaces';
import { Sifchain } from '../../chains/sifchain/sifchain';
import { Token as CosmosToken } from '../../services/cosmos-base';
import { logger } from '../../services/logger';

export class SifchainConnector implements SifchainishConnector {
  private static _instances: { [name: string]: SifchainConnector };
  private sifchain: Sifchain;
  public chain: string;
  private _router: string;
  // private _routerAbi: ContractInterface;
  private _gasLimit: number;
  private _ttl: number;
  private tokenList: Record<string, CosmosToken> = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    this.chain = chain;
    const config = SifchainConnectorConfig.config;
    this.sifchain = Sifchain.getInstance(network);
    this._router = config.routerAddress(network);
    this._ttl = config.ttl;
    // this._routerAbi = routerAbi.abi;
    this._gasLimit = config.gasLimit;
  }

  public static getInstance(chain: string, network: string): SifchainConnector {
    if (SifchainConnector._instances === undefined) {
      SifchainConnector._instances = {};
    }
    if (!(chain + network in SifchainConnector._instances)) {
      SifchainConnector._instances[chain + network] = new SifchainConnector(
        chain,
        network
      );
    }

    return SifchainConnector._instances[chain + network];
  }

  /**
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address CosmosToken address
   */
  public getTokenByAddress(address: string): CosmosToken {
    return this.tokenList[address];
  }

  public async init() {
    if (this.chain == 'sifchain' && !this.sifchain.ready())
      throw new Error('Sifchain is not available');
    for (const token of this.sifchain.storedTokenList) {
      this.tokenList[token.address] = {
        base: token.base,
        address: token.address,
        decimals: token.decimals,
        symbol: token.symbol,
        name: token.name,
      };
    }
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  public get router(): string {
    return this._router;
  }

  public get ttl(): number {
    return this._ttl;
  }

  // public get routerAbi(): ContractInterface {
  //   return this._routerAbi;
  // }

  public get gasLimit(): number {
    return this._gasLimit;
  }

  /**
   * Gets the allowed slippage percent from the optional parameter or the value
   * in the configuration.
   *
   * @param allowedSlippageStr (Optional) should be of the form '1/10'.
   */
  public getAllowedSlippage(allowedSlippageStr?: string): Percent {
    if (allowedSlippageStr != null && isFractionString(allowedSlippageStr)) {
      return eval(allowedSlippageStr);
    }

    const allowedSlippage = SifchainConnectorConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return eval(nd[0]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  /**
   * Given the amount of `baseToken` to put into a transaction, calculate the
   * amount of `quoteToken` that can be expected from the transaction.
   *
   * This is typically used for calculating token sell prices.
   *
   * @param baseToken Token input for the transaction
   * @param quoteToken Output from the transaction
   * @param amount Amount of `baseToken` to put into the transaction
   */
  async estimateSellTrade(
    baseToken: Token,
    quoteToken: Token,
    amount: string
  ): Promise<ExpectedTrade | string> {
    /*
      There are huge differences between the returned value of this function and the one returned from https://sifchain.akash.pro/#/swap?from=uatom&to=rowan&slippage=1.0
      price impact and liquidity provider fees are almost the same
    */
    logger.info(
      `Fetching pair data for ${baseToken.address}-${quoteToken.address}.`
    );

    const signingClient = await this.sifchain._signingClient;

    const swap = await signingClient.simulateSwap(
      {
        denom: baseToken.denom,
        amount: Decimal.fromUserInput(amount, baseToken.decimals.low).atomics,
      },
      { denom: quoteToken.denom },
      this.getAllowedSlippage()
    );

    const rawReceiving = swap.rawReceiving.toFloatApproximation();
    const minimumReceiving = swap.minimumReceiving.toFloatApproximation();
    const liquidityProviderFee =
      swap.liquidityProviderFee.toFloatApproximation();
    const priceImpact = swap.priceImpact;

    return {
      rawReceiving,
      minimumReceiving,
      liquidityProviderFee,
      priceImpact,
    };
  }

  /**
   * Given the amount of `baseToken` desired to acquire from a transaction,
   * calculate the amount of `quoteToken` needed for the transaction.
   *
   * This is typically used for calculating token buy prices.
   *
   * @param quoteToken Token input for the transaction
   * @param baseToken Token output from the transaction
   * @param amount Amount of `baseToken` desired from the transaction
   */
  async estimateBuyTrade(
    quoteToken: Token,
    baseToken: Token,
    amount: string
  ): Promise<ExpectedTrade | string> {
    /* We want to buy 100 atom, how many rowans do we need and what are the fees? */
    /*
      This currently takes the rowan per atom price and multiplies it by the amount of atoms we want to buy. 
      Then runs a simulation to get the fees, the problem is that the received amount is always less than the amount we want to buy.

      What sdk does https://sifchain.akash.pro/#/swap?from=uatom&to=c1inch&slippage=1.0? We are able to write how much we want to buy there and it calculates the fees.
    */
    logger.info(
      `Fetching pair data for ${quoteToken.baseDenom}-${baseToken.baseDenom}.`
    );

    const signingClient = await this.sifchain._signingClient;

    const quoteTokenPerBaseToken = await signingClient.simulateSwap(
      {
        denom: baseToken.denom,
        amount: Decimal.fromUserInput('1', baseToken.decimals.low).atomics,
      },
      { denom: quoteToken.denom },
      this.getAllowedSlippage()
    );

    const TotalQuoteTokenNeeded =
      quoteTokenPerBaseToken.rawReceiving.toFloatApproximation() * amount;

    const swap = await signingClient.simulateSwap(
      {
        denom: quoteToken.denom,
        amount: Decimal.fromUserInput(
          TotalQuoteTokenNeeded.toFixed(quoteToken.decimals.low),
          quoteToken.decimals.low
        ).atomics,
      },
      { denom: baseToken.denom },
      this.getAllowedSlippage()
    );

    const rawReceiving = swap.rawReceiving.toFloatApproximation();
    const minimumReceiving = swap.minimumReceiving.toFloatApproximation();
    const liquidityProviderFee =
      swap.liquidityProviderFee.toFloatApproximation();
    const priceImpact = swap.priceImpact;

    return {
      rawReceiving,
      minimumReceiving,
      liquidityProviderFee,
      priceImpact,
    };
  }
}
