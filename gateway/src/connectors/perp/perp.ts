import {
  InitializationError,
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

export class Perp {
  private static _instances: { [name: string]: Perp };
  private ethereum: Ethereum;
  private _perp: PerpetualProtocol;
  private _wallet?: Wallet;
  private _chain: string;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string, wallet?: Wallet) {
    this._chain = chain;
    this.ethereum = Ethereum.getInstance(network);
    this.chainId = this.ethereum.chainId;
    this._perp = new PerpetualProtocol({
      chainId: this.chainId,
      providerConfigs: [{ rpcUrl: this.ethereum.rpcUrl }],
    });
    this._wallet = wallet;
  }

  public static getInstance(
    chain: string,
    network: string,
    wallet?: Wallet
  ): Perp {
    if (Perp._instances === undefined) {
      Perp._instances = {};
    }

    let address = '';
    if (wallet) address = wallet.address;

    if (!(chain + network + address in Perp._instances)) {
      Perp._instances[chain + network + address] = new Perp(
        chain,
        network,
        wallet
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
    if (this._wallet) {
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
    if (nd) return Number(nd[0]) / Number(nd[1]);
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
   * @param pair Market pair
   */
  async prices(pair: string): Promise<{
    markPrice: Big;
    indexPrice: Big;
    indexTwapPrice: Big;
  }> {
    const tickerSymbol = pair.replace('-', '');
    const market = this._perp.markets.getMarket({ tickerSymbol });
    return await market.getPrices();
  }

  /**
   * Used to know if a market is active/tradable.
   * @param pair Market pair
   * @returns true | false
   */
  async isMarketActive(pair: string): Promise<boolean> {
    const tickerSymbol = pair.replace('-', '');
    const market = this._perp.markets.getMarket({ tickerSymbol });
    return (await market.getStatus()) === MarketStatus.ACTIVE ? true : false;
  }

  /**
   * Gets available Positions/Position.
   * @param tickerSymbol An optional parameter to get specific position.
   * @returns Return all Positions or specific position.
   */
  async getPositions(
    tickerSymbol?: string
  ): Promise<Positions | Position | undefined> {
    const positions = this._perp.positions;
    if (positions && tickerSymbol) {
      return await positions.getTakerPositionByTickerSymbol(tickerSymbol);
    }
    return positions;
  }

  async openPosition(
    isLong: boolean,
    tickerSymbol: string,
    minBaseAmount: string
  ): Promise<Transaction> {
    const slippage = new Big(this.getAllowedSlippage());
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

  async closePosition(tickerSymbol: string): Promise<Transaction> {
    const slippage = new Big(this.getAllowedSlippage());
    const clearingHouse = this._perp.clearingHouse as ClearingHouse;
    const position = await this.getPositions(tickerSymbol);
    if (!position) {
      throw new Error(`No active position on ${tickerSymbol}.`);
    }
    return (await clearingHouse.closePosition(position as Position, slippage))
      .transaction;
  }
}
