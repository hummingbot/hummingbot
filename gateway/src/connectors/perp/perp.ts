import {
  HttpException,
  InitializationError,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { isFractionString } from '../../services/validators';
import { PerpConfig } from './perp.config';
import {
  PerpetualProtocol,
  MarketStatus,
  Position,
  Positions,
  PositionSide,
  ClearingHouse,
} from '@perp/sdk-curie';
import { Token } from '@uniswap/sdk';
import { Big } from 'big.js';
import { Transaction, Wallet } from 'ethers';
import { logger } from '../../services/logger';
import { percentRegexp } from '../../services/config-manager-v2';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { Perpish } from '../../services/common-interfaces';

export interface PerpPosition {
  positionAmt: string;
  positionSide: string;
  unrealizedProfit: string;
  leverage: string;
  entryPrice: string;
  tickerSymbol: string;
  pendingFundingPayment: string;
}

export class Perp implements Perpish {
  private static _instances: { [name: string]: Perp };
  private ethereum: Ethereum;
  private _perp: PerpetualProtocol;
  private _address: string;
  private _wallet?: Wallet;
  private _chain: string;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;
  public gasLimit = 16000000; // Default from perpfi https://github.com/perpetual-protocol/sdk-curie/blob/6211010ce6ddeb24312085775fc7e64336e426da/src/transactionSender/index.ts#L44

  private constructor(chain: string, network: string, address?: string) {
    this._chain = chain;
    this.ethereum = Ethereum.getInstance(network);
    this.chainId = this.ethereum.chainId;
    this._perp = new PerpetualProtocol({
      chainId: this.chainId,
      providerConfigs: [{ rpcUrl: this.ethereum.rpcUrl }],
    });
    this._address = address ? address : '';
  }

  public get perp(): PerpetualProtocol {
    return this._perp;
  }

  public static getInstance(
    chain: string,
    network: string,
    address?: string
  ): Perp {
    if (Perp._instances === undefined) {
      Perp._instances = {};
    }

    if (!(chain + network + address in Perp._instances)) {
      Perp._instances[chain + network + address] = new Perp(
        chain,
        network,
        address
      );
    }

    return Perp._instances[chain + network + address];
  }

  /**
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address Token address
   */
  public getTokenByAddress(address: string): Token {
    return this.tokenList[address];
  }

  public async init() {
    if (this._chain == 'ethereum' && !this.ethereum.ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    for (const token of this.ethereum.storedTokenList) {
      this.tokenList[token.address] = new Token(
        this.chainId,
        token.address,
        token.decimals,
        token.symbol,
        token.name
      );
    }
    await this._perp.init();
    if (this._address !== '') {
      try {
        this._wallet = await this.ethereum.getWallet(this._address);
      } catch (err) {
        logger.error(`Wallet ${this._address} not available.`);
        throw new HttpException(
          500,
          LOAD_WALLET_ERROR_MESSAGE + err,
          LOAD_WALLET_ERROR_CODE
        );
      }

      await this._perp.connect({ signer: this._wallet });
      logger.info(
        `${this._wallet.address} wallet connected on perp ${this._chain}.`
      );
    }
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  /**
   * Gets the allowed slippage percent from the optional parameter or the value
   * in the configuration.
   *
   * @param allowedSlippageStr (Optional) should be of the form '1/10'.
   */
  public getAllowedSlippage(allowedSlippageStr?: string): number {
    let allowedSlippage;
    if (allowedSlippageStr != null && isFractionString(allowedSlippageStr)) {
      allowedSlippage = allowedSlippageStr;
    } else allowedSlippage = PerpConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return Number(nd[1]) / Number(nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  /**
   * @returns a list of available marker pairs.
   */
  availablePairs(): string[] {
    return Object.keys(this._perp.markets.marketMap);
  }

  /**
   * Queries for the market, index and indexTwap prices for a given market pair.
   * @param tickerSymbol Market pair
   */
  async prices(tickerSymbol: string): Promise<{
    markPrice: Big;
    indexPrice: Big;
    indexTwapPrice: Big;
  }> {
    const market = this._perp.markets.getMarket({ tickerSymbol });
    return await market.getPrices({ cache: false });
  }

  /**
   * Used to know if a market is active/tradable.
   * @param tickerSymbol Market pair
   * @returns true | false
   */
  async isMarketActive(tickerSymbol: string): Promise<boolean> {
    const market = this._perp.markets.getMarket({ tickerSymbol });
    return (await market.getStatus()) === MarketStatus.ACTIVE ? true : false;
  }

  /**
   * Gets available Position.
   * @param tickerSymbol An optional parameter to get specific position.
   * @returns Return all Positions or specific position.
   */
  async getPositions(tickerSymbol: string): Promise<PerpPosition | undefined> {
    const positions = this._perp.positions;
    let positionAmt: string = '0',
      positionSide: string = '',
      unrealizedProfit: string = '0',
      leverage: string = '1',
      entryPrice: string = '0',
      pendingFundingPayment: string = '0';
    if (positions && tickerSymbol) {
      const fp = await positions.getTotalPendingFundingPayments({
        cache: false,
      });
      for (const [key, value] of Object.entries(fp)) {
        if (key === tickerSymbol) pendingFundingPayment = value.toString();
      }

      const position = await positions.getTakerPositionByTickerSymbol(
        tickerSymbol,
        { cache: false }
      );
      if (position) {
        positionSide = PositionSide[position.side];
        unrealizedProfit = (
          await position.getUnrealizedPnl({ cache: false })
        ).toString();
        leverage = '1';
        entryPrice = position.entryPrice.toString();
        positionAmt = position.sizeAbs.toString();
      }
    }
    return {
      positionAmt,
      positionSide,
      unrealizedProfit,
      leverage,
      entryPrice,
      tickerSymbol,
      pendingFundingPayment,
    };
  }

  /**
   * Given the necessary parameters, open a position.
   * @param isLong Will create a long position if true, else a short pos will be created.
   * @param tickerSymbol the market to create position on.
   * @param minBaseAmount the min amount for the position to be opened.
   * @returns An ethers transaction object.
   */
  async openPosition(
    isLong: boolean,
    tickerSymbol: string,
    minBaseAmount: string,
    allowedSlippage?: string
  ): Promise<Transaction> {
    let slippage: Big;
    if (allowedSlippage)
      slippage = new Big(this.getAllowedSlippage(allowedSlippage).toString());
    else slippage = new Big(this.getAllowedSlippage().toString());
    const amountInput = new Big(minBaseAmount);
    const side = isLong ? PositionSide.LONG : PositionSide.SHORT;
    const isAmountInputBase = false; // we are not using base token to open position.
    const clearingHouse = this._perp.clearingHouse as ClearingHouse;

    const newPositionDraft = clearingHouse.createPositionDraft({
      tickerSymbol,
      side,
      amountInput,
      isAmountInputBase,
    });
    return (await clearingHouse.openPosition(newPositionDraft, slippage))
      .transaction;
  }

  /**
   * Closes an open position on the specified market.
   * @param tickerSymbol The market on which we want to close position.
   * @returns An ethers transaction object.
   */
  async closePosition(
    tickerSymbol: string,
    allowedSlippage?: string
  ): Promise<Transaction> {
    let slippage: Big;
    if (allowedSlippage)
      slippage = new Big(this.getAllowedSlippage(allowedSlippage).toString());
    else slippage = new Big(this.getAllowedSlippage().toString());
    const clearingHouse = this._perp.clearingHouse as ClearingHouse;
    const positions = this._perp.positions as Positions;
    const position = await positions.getTakerPositionByTickerSymbol(
      tickerSymbol
    );
    if (!position) {
      throw new Error(`No active position on ${tickerSymbol}.`);
    }
    return (await clearingHouse.closePosition(position as Position, slippage))
      .transaction;
  }

  /**
   * Function for getting account value
   * @returns account value
   */
  async getAccountValue(): Promise<Big> {
    const clearingHouse = this._perp.clearingHouse as ClearingHouse;
    return await clearingHouse.getAccountValue();
  }
}
