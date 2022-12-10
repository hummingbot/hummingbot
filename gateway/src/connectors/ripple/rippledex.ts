// import { RippleDEXConfig } from './rippledex.config';
// import {
//   Config as RippleConfig,
//   getRippleConfig,
// } from '../../chains/ripple/ripple.config';
import { Ripple } from '../../chains/ripple/ripple';
import {
  Client,
  OfferCancel,
  Transaction,
  xrpToDrops,
  AccountInfoResponse,
  BookOffersResponse,
} from 'xrpl';
import {
  Market,
  MarketNotFoundError,
  IMap,
  GetTickerResponse,
  Ticker,
  GetOrderBookResponse,
} from './rippledex.types';
import { promiseAllInBatches } from '../serum/serum.helpers';

export type RippleDEXish = RippleDEX;

export class RippleDEX {
  private static _instances: { [name: string]: RippleDEX };
  // private initializing: boolean = false;

  // private readonly config: RippleDEXConfig.Config;
  // private readonly rippleConfig: RippleConfig;
  private readonly _client: Client;
  private readonly _ripple: Ripple;
  // private ripple!: Ripple;
  private _ready: boolean = false;

  chain: string;
  network: string;
  readonly connector: string = 'rippleDEX';

  /**
   * Creates a new instance of Serum.
   *
   * @param chain
   * @param network
   * @private
   */
  private constructor(chain: string, network: string) {
    this.chain = chain;
    this.network = network;

    // this.config = RippleDEXConfig.config;
    // this._rippleConfig = getRippleConfig(chain, network);

    this._ripple = Ripple.getInstance(network);

    this._client = this._ripple.client;

    if (!this._client.isConnected()) {
      this._client.connect();
    }
  }

  public static getInstance(chain: string, network: string): RippleDEX {
    if (RippleDEX._instances === undefined) {
      RippleDEX._instances = {};
    }
    if (!(network in RippleDEX._instances)) {
      RippleDEX._instances[network] = new RippleDEX(chain, network);
    }

    return RippleDEX._instances[network];
  }

  /**
   * @param name
   */
  async getMarket(name?: string): Promise<Market> {
    if (!name) throw new MarketNotFoundError(`No market informed.`);
    // Market name format:
    // 1: "ETH.rcA8X3TVMST1n3CJeAdGk1RdRCHii7N2h/USD.rcA8X3TVMST1n3CJeAdGk1RdRCHii7N2h"
    // 2: "XRP/ETH.rcA8X3TVMST1n3CJeAdGk1RdRCHii7N2h"
    // 3: "ETH.rcA8X3TVMST1n3CJeAdGk1RdRCHii7N2h/XRP"
    let baseTickSize: number;
    let baseTransferRate: number;
    let quoteTickSize: number;
    let quoteTransferRate: number;
    let baseMarketResp: AccountInfoResponse | undefined;
    let quoteMarketResp: AccountInfoResponse | undefined;
    const zeroTransferRate = 1000000000;

    const [base, quote] = name.split('/');

    const [baseCurrency, baseIssuer] = base.split('.');
    const [quoteCurrency, quoteIssuer] = quote.split('.');

    if (baseCurrency != 'XRP') {
      const baseMarketResp: AccountInfoResponse = await this._client.request({
        command: 'account_info',
        ledger_index: 'validated',
        account: baseIssuer,
      });
      baseTickSize = baseMarketResp.result.account_data.TickSize ?? 15;
      const rawTransferRate =
        baseMarketResp.result.account_data.TransferRate ?? zeroTransferRate;
      baseTransferRate = rawTransferRate / zeroTransferRate - 1;
    } else {
      baseTickSize = 15;
      baseTransferRate = 0;
    }

    if (quoteCurrency != 'XRP') {
      const quoteMarketResp: AccountInfoResponse = await this._client.request({
        command: 'account_info',
        ledger_index: 'validated',
        account: quoteIssuer,
      });
      quoteTickSize = quoteMarketResp.result.account_data.TickSize ?? 15;
      const rawTransferRate =
        quoteMarketResp.result.account_data.TransferRate ?? zeroTransferRate;
      quoteTransferRate = rawTransferRate / zeroTransferRate - 1;
    } else {
      quoteTickSize = 15;
      quoteTransferRate = 0;
    }

    const smallestTickSize = Math.min(baseTickSize, quoteTickSize);
    const returnTickSize = Number(`1e-${smallestTickSize}`);
    const minimumOrderSize = returnTickSize;

    if (!baseMarketResp)
      throw new MarketNotFoundError(`Market "${base}" not found.`);
    if (!quoteMarketResp)
      throw new MarketNotFoundError(`Market "${quote}" not found.`);

    return {
      name: name,
      minimumOrderSize: minimumOrderSize,
      tickSize: returnTickSize,
      baseTransferRate: baseTransferRate,
      quoteTransferRate: quoteTransferRate,
    };
  }

  /**
   * @param names
   */
  async getMarkets(names: string[]): Promise<IMap<string, Market>> {
    const markets = IMap<string, Market>().asMutable();

    const getMarket = async (name: string): Promise<void> => {
      const market = await this.getMarket(name);

      markets.set(name, market);
    };

    await promiseAllInBatches(getMarket, names);

    return markets;
  }

  /**
   * Returns the last traded prices.
   */
  async getTicker(marketName: string): Promise<GetTickerResponse> {
    const [base, quote] = marketName.split('/');
    const [baseCurrency, baseIssuer] = base.split('.');
    const [quoteCurrency, quoteIssuer] = quote.split('.');

    const baseRequest: any = {
      currency: baseCurrency,
    };

    const quoteRequest: any = {
      currency: quoteCurrency,
    };

    if (baseIssuer) {
      baseRequest['issuer'] = baseIssuer;
    }
    if (quoteIssuer) {
      quoteRequest['issuer'] = quoteIssuer;
    }

    const orderbook_resp_ask: any = await this._client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: baseRequest,
      taker_pays: quoteRequest,
      limit: 1,
    });

    const orderbook_resp_bid: any = await this._client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: quoteRequest,
      taker_pays: baseRequest,
      limit: 1,
    });

    const asks = orderbook_resp_ask.result.offers;
    const bids = orderbook_resp_bid.result.offers;

    let topAsk = 0;
    let topBid = 0;

    if (baseCurrency === 'XRP' || quoteCurrency === 'XRP') {
      topAsk = asks[0].quality ? Number(asks[0].quality) / 1000000 : 0;
      topBid = bids[0].quality ? 1 / Number(bids[0].quality) / 1000000 : 0;
    } else {
      topAsk = asks[0].quality ? Number(asks[0].quality) : 0;
      topBid = bids[0].quality ? 1 / Number(bids[0].quality) : 0;
    }

    const midPrice = (topAsk + topBid) / 2;

    return {
      price: midPrice,
      timestamp: Date.now(),
    };
  }

  async getTickers(marketNames: string[]): Promise<IMap<string, Ticker>> {
    const tickers = IMap<string, Ticker>().asMutable();

    const getTicker = async (marketName: string): Promise<void> => {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    };

    await promiseAllInBatches(getTicker, marketNames);

    return tickers;
  }

  async getOrderBook(
    marketName: string,
    limit: number
  ): Promise<GetOrderBookResponse> {
    const market = await this.getMarket(marketName);

    const [base, quote] = marketName.split('/');

    const [baseCurrency, baseIssuer] = base.split('.');
    const [quoteCurrency, quoteIssuer] = quote.split('.');

    const baseRequest: any = {
      currency: baseCurrency,
    };

    const quoteRequest: any = {
      currency: quoteCurrency,
    };

    if (baseIssuer) {
      baseRequest['issuer'] = baseIssuer;
    }
    if (quoteIssuer) {
      quoteRequest['issuer'] = quoteIssuer;
    }

    const orderbook_resp_ask: BookOffersResponse = await this._client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: baseRequest,
      taker_pays: quoteRequest,
      limit: limit,
    });

    const orderbook_resp_bid: BookOffersResponse = await this._client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: quoteRequest,
      taker_pays: baseRequest,
      limit: limit,
    });

    const asks = orderbook_resp_ask.result.offers;
    const bids = orderbook_resp_bid.result.offers;

    let topAsk = 0;
    let topBid = 0;

    if (baseCurrency === 'XRP' || quoteCurrency === 'XRP') {
      topAsk = asks[0].quality ? Number(asks[0].quality) / 1000000 : 0;
      topBid = bids[0].quality ? 1 / Number(bids[0].quality) / 1000000 : 0;
    } else {
      topAsk = asks[0].quality ? Number(asks[0].quality) : 0;
      topBid = bids[0].quality ? 1 / Number(bids[0].quality) : 0;
    }

    const midPrice = (topAsk + topBid) / 2;

    return {
      market,
      asks,
      bids,
      topAsk,
      topBid,
      midPrice,
      timestamp: Date.now(),
    };
  }

  async getOrderBooks(
    marketNames: string[],
    limit: number
  ): Promise<IMap<string, GetOrderBookResponse>> {
    const orderBooks = IMap<string, GetOrderBookResponse>().asMutable();

    const getOrderBook = async (marketName: string): Promise<void> => {
      const orderBook = await this.getOrderBook(marketName, limit);

      orderBooks.set(marketName, orderBook);
    };

    await promiseAllInBatches(getOrderBook, marketNames);

    return orderBooks;
  }

  async getOrders(tx: string): Promise<any> {
    const tx_resp = await this._client.request({
      command: 'tx',
      transaction: tx,
      binary: false,
    });

    const result = tx_resp.result;

    return result;
  }

  async createOrders(
    walletAddress: string,
    base: any,
    quote: any,
    side: string,
    price: number,
    amount: number
  ): Promise<any> {
    const ripple = Ripple.getInstance(this.network);
    const wallet = await ripple.getWallet(walletAddress);
    const total = price * amount;
    let we_pay = {
      currency: '',
      issuer: '',
      value: '',
    };
    let we_get = { currency: '', issuer: '', value: '' };

    if (side == 'BUY') {
      we_pay = {
        currency: base.currency,
        issuer: base.issuer,
        value: total.toString(),
      };
      we_get = {
        currency: quote.currency,
        issuer: quote.issuer,
        value: amount.toString(),
      };
    } else {
      we_pay = {
        currency: quote.currency,
        issuer: quote.issuer,
        value: total.toString(),
      };
      we_get = {
        currency: base.currency,
        issuer: base.issuer,
        value: amount.toString(),
      };
    }

    if (we_pay.currency == 'XRP') {
      we_pay.value = xrpToDrops(we_pay.value);
    }

    if (we_get.currency == 'XRP') {
      we_get.value = xrpToDrops(we_get.value);
    }

    const offer: Transaction = {
      TransactionType: 'OfferCreate',
      Account: wallet.classicAddress,
      TakerPays: we_pay,
      TakerGets: we_get.currency == 'XRP' ? we_get.value : we_get,
    };

    const prepared = await this._client.autofill(offer);
    console.log('Prepared transaction:', JSON.stringify(prepared, null, 2));
    const signed = wallet.sign(prepared);
    console.log('Sending OfferCreate transaction...');
    const response = await this._client.submitAndWait(signed.tx_blob);

    return response;
  }

  async cancelOrders(
    walletAddress: string,
    offerSequence: number
  ): Promise<any> {
    const ripple = Ripple.getInstance(this.network);
    const wallet = await ripple.getWallet(walletAddress);
    const request: OfferCancel = {
      TransactionType: 'OfferCancel',
      Account: wallet.classicAddress,
      OfferSequence: offerSequence,
    };

    const prepared = await this._client.autofill(request);
    console.log('Prepared transaction:', JSON.stringify(prepared, null, 2));
    const signed = wallet.sign(prepared);
    console.log('Sending OfferCancel transaction...');
    const response = await this._client.submitAndWait(signed.tx_blob);

    return response;
  }

  async getOpenOrders(address: string): Promise<any> {
    const account_offers_resp = await this._client.request({
      command: 'account_offers',
      account: address,
    });

    const result = account_offers_resp.result;

    return result;
  }

  ready(): boolean {
    return this._ready;
  }

  isConnected(): boolean {
    return this._client.isConnected();
  }

  public get client() {
    return this._client;
  }
}
