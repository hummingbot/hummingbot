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
import { BigNumber } from 'ethers/lib/ethers';
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
      const fractionSplit = allowedSlippageStr.split('/');
      return new Percent(fractionSplit[0], fractionSplit[1]);
    }

    const allowedSlippage = SifchainConnectorConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return new Percent(nd[1], nd[2]);
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
    // SELL - 100 ATOM
    baseToken: Token, // ATOM
    quoteToken: Token, // ROWAN
    amount: BigNumber
  ): Promise<ExpectedTrade | string> {
    // I WANT TO SELL 100 ATOM FOR ROWAN
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
      this.getAllowedSlippage() // Slippage
    );

    console.log(baseToken);
    console.log(quoteToken);
    // console.log(swap);

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
    // BUY
    quoteToken: Token, // ROWAN
    baseToken: Token, // ATOM
    amount: string // I want to buy 100 ATOM, how much ROWAN do I need?
  ): Promise<ExpectedTrade | string> {
    logger.info(
      `Fetching pair data for ${quoteToken.baseDenom}-${baseToken.baseDenom}.`
    );

    const signingClient = await this.sifchain._signingClient;

    // TODO: response has wrong values - https://sifchain-dex.redstarling.com/#/swap?from=c1inch&to=cuma&slippage=1.0
    // USDT per ATOM price
    const usdtPerAtom = await signingClient.simulateSwap(
      {
        denom: baseToken.denom,
        amount: Decimal.fromUserInput('1', baseToken.decimals.low).atomics,
      },
      { denom: quoteToken.denom },
      this.getAllowedSlippage() // Slippage
    );

    console.log(usdtPerAtom);

    const atomPerRowan = await signingClient.simulateSwap(
      {
        denom: quoteToken.denom,
        amount: Decimal.fromUserInput('1', quoteToken.decimals.low).atomics,
      },
      { denom: baseToken.denom },
      this.getAllowedSlippage() // Slippage
    );

    console.log(atomPerRowan.rawReceiving.toFloatApproximation());

    // const pricePerquoteToken = inchPrice.rawReceiving.toFloatApproximation();
    // const usdtPerAtomPrice = usdtPerAtom.rawReceiving.toFloatApproximation();

    // console.log(usdtPerAtomPrice);
    // console.log(
    //   (usdtPerAtomPrice / amount).toFixed(baseToken.decimals.low) +
    //     ' ATOM for 10000 ROWAN'
    // );

    // 100/0.000626
    // amount that i need to buy (amount)/atomPerRowan
    // 159662,1021606584
    // BUY 100 atom, how much rowan do I need to buy 100 atoms?
    // SELL 100 atom, how much rowan do I get? +
    const swap = await signingClient.simulateSwap(
      {
        denom: baseToken.denom,
        amount: Decimal.fromUserInput(amount, baseToken.decimals.low).atomics,
      },
      { denom: quoteToken.denom },
      this.getAllowedSlippage() // Slippage
    );

    console.log(swap);
    console.log(swap.rawReceiving.toFloatApproximation());
    console.log(swap.minimumReceiving.toFloatApproximation());
    console.log(swap.liquidityProviderFee.toFloatApproximation());

    return;
  }
}
