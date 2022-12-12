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
  TransactionMetadata,
} from 'xrpl';
import {
  Market,
  MarketNotFoundError,
  IMap,
  GetTickerResponse,
  Ticker,
  GetOrderBookResponse,
  Token,
  CreateOrderResponse,
  OrderStatus,
  CreateOrderRequest,
  CancelOrderRequest,
  CancelOrderResponse,
  GetOpenOrderRequest,
  GetOpenOrderResponse,
  GetOpenOrdersResponse,
  OrderSide,
} from './rippledex.types';
import { promiseAllInBatches } from '../serum/serum.helpers';
import { isIssuedCurrency } from 'xrpl/dist/npm/models/transactions/common';

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

  async createOrder(order: CreateOrderRequest): Promise<CreateOrderResponse> {
    const [base, quote] = order.marketName.split('/');
    const [baseCurrency, baseIssuer] = base.split('.');
    const [quoteCurrency, quoteIssuer] = quote.split('.');

    const market = await this.getMarket(order.marketName);

    const ripple = Ripple.getInstance(this.network);
    const wallet = await ripple.getWallet(order.walletAddress);
    const total = order.price * order.amount;
    let fee = 0;

    let we_pay: Token = {
      currency: '',
      issuer: '',
      value: '',
    };
    let we_get: Token = { currency: '', issuer: '', value: '' };

    if (order.side == 'BUY') {
      we_pay = {
        currency: baseCurrency,
        issuer: baseIssuer,
        value: total.toString(),
      };
      we_get = {
        currency: quoteCurrency,
        issuer: quoteIssuer,
        value: order.amount.toString(),
      };

      fee = market.baseTransferRate;
    } else {
      we_pay = {
        currency: quoteCurrency,
        issuer: quoteIssuer,
        value: total.toString(),
      };
      we_get = {
        currency: baseCurrency,
        issuer: baseIssuer,
        value: order.amount.toString(),
      };

      fee = market.quoteTransferRate;
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
      TakerPays: we_pay.currency == 'XRP' ? we_pay.value : we_pay,
      TakerGets: we_get.currency == 'XRP' ? we_get.value : we_get,
    };

    if (order.sequence != undefined) {
      offer.OfferSequence = order.sequence;
    }

    const prepared = await this._client.autofill(offer);
    const signed = wallet.sign(prepared);
    const response = await this._client.submitAndWait(signed.tx_blob);

    let orderStatus = OrderStatus.UNKNOWN;
    let orderSequence = -1;
    let orderLedgerIndex = '';

    if (response.result) {
      const meta = response.result.meta;
      if (meta) {
        const affectedNodes = (meta as TransactionMetadata).AffectedNodes;

        for (const affnode of affectedNodes) {
          if ('ModifiedNode' in affnode) {
            if (affnode.ModifiedNode.LedgerEntryType == 'Offer') {
              // Usually a ModifiedNode of type Offer indicates a previous Offer that
              // was partially consumed by this one.
              orderStatus = OrderStatus.FILLED;
            }
          } else if ('DeletedNode' in affnode) {
            if (affnode.DeletedNode.LedgerEntryType == 'Offer') {
              // The removed Offer may have been fully consumed, or it may have been
              // found to be expired or unfunded.
              orderStatus = OrderStatus.FILLED;
            }
          } else if ('CreatedNode' in affnode) {
            if (affnode.CreatedNode.LedgerEntryType == 'Offer') {
              // Created an Offer object on the Ledger
              orderStatus = OrderStatus.OPEN;
              orderSequence = response.result.Sequence ?? -1;
              orderLedgerIndex = affnode.CreatedNode.LedgerIndex;
            }
          }
        }
      }
    }

    const returnResponse: CreateOrderResponse = {
      walletAddress: order.walletAddress,
      marketName: order.marketName,
      price: order.price,
      amount: order.amount,
      side: order.side,
      type: order.type,
      fee,
      orderLedgerIndex: orderLedgerIndex,
      status: orderStatus,
      sequence: orderSequence,
      signature: response.result.hash,
    };

    return returnResponse;
  }

  async createOrders(
    orders: CreateOrderRequest[]
  ): Promise<IMap<number, CreateOrderResponse>> {
    const createdOrders = IMap<number, CreateOrderResponse>().asMutable();

    const getCreatedOrders = async (
      order: CreateOrderRequest
    ): Promise<void> => {
      const createdOrder = await this.createOrder(order);

      createdOrders.set(createdOrder.sequence, createdOrder);
    };

    await promiseAllInBatches(getCreatedOrders, orders);

    return createdOrders;
  }

  async cancelOrder(order: CancelOrderRequest): Promise<CancelOrderResponse> {
    const ripple = Ripple.getInstance(this.network);
    const wallet = await ripple.getWallet(order.walletAddress);
    const request: OfferCancel = {
      TransactionType: 'OfferCancel',
      Account: wallet.classicAddress,
      OfferSequence: order.offerSequence,
    };

    const prepared = await this._client.autofill(request);
    const signed = wallet.sign(prepared);
    const response = await this._client.submitAndWait(signed.tx_blob);

    let orderStatus = OrderStatus.CANCELATION_PENDING;

    if (response.result) {
      const meta = response.result.meta;
      if (meta) {
        const affectedNodes = (meta as TransactionMetadata).AffectedNodes;

        for (const affnode of affectedNodes) {
          if ('DeletedNode' in affnode) {
            if (affnode.DeletedNode.LedgerEntryType == 'Offer') {
              orderStatus = OrderStatus.CANCELED;
            }
          }
        }
      }
    }

    const returnResponse: CancelOrderResponse = {
      walletAddress: order.walletAddress,
      status: orderStatus,
      signature: response.result.hash,
    };

    return returnResponse;
  }

  async cancelOrders(
    orders: CancelOrderRequest[]
  ): Promise<IMap<number, CancelOrderResponse>> {
    const cancelledOrders = IMap<number, CancelOrderResponse>().asMutable();

    const getCancelledOrders = async (
      order: CancelOrderRequest
    ): Promise<void> => {
      const cancelledOrder = await this.cancelOrder(order);

      cancelledOrders.set(order.offerSequence, cancelledOrder);
    };

    await promiseAllInBatches(getCancelledOrders, orders);

    return cancelledOrders;
  }

  async getOpenOrders(params: {
    market?: GetOpenOrderRequest;
    markets?: GetOpenOrderRequest[];
  }): Promise<GetOpenOrdersResponse> {
    const openOrders = IMap<
      string,
      IMap<number, GetOpenOrderResponse>
    >().asMutable();

    const marketArray: GetOpenOrderRequest[] = [];
    if (params.market) marketArray.push(params.market);
    if (params.markets) marketArray.concat(params.markets);

    for (const market of marketArray) {
      const [base, quote] = market.marketName.split('/');

      const [baseCurrency, baseIssuer] = base.split('.');
      const [quoteCurrency, quoteIssuer] = quote.split('.');

      const openOrdersInMarket = IMap<
        number,
        GetOpenOrderResponse
      >().asMutable();

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

      const orderbook_resp_ask: BookOffersResponse = await this._client.request(
        {
          command: 'book_offers',
          ledger_index: 'validated',
          taker: market.walletAddress,
          taker_gets: baseRequest,
          taker_pays: quoteRequest,
        }
      );

      const orderbook_resp_bid: BookOffersResponse = await this._client.request(
        {
          command: 'book_offers',
          ledger_index: 'validated',
          taker: market.walletAddress,
          taker_gets: quoteRequest,
          taker_pays: baseRequest,
        }
      );

      const asks = orderbook_resp_ask.result.offers;
      const bids = orderbook_resp_bid.result.offers;

      for (const ask of asks) {
        const price = ask.quality ?? '-1';
        let amount: string = '';

        if (isIssuedCurrency(ask.TakerGets)) {
          amount = ask.TakerGets.value;
        } else {
          amount = ask.TakerGets;
        }
        openOrdersInMarket.set(ask.Sequence, {
          sequence: ask.Sequence,
          marketName: market.marketName,
          price: price,
          amount: amount,
          side: OrderSide.SELL,
        });
      }

      for (const bid of bids) {
        const price = Math.pow(Number(bid.quality), -1).toString() ?? '-1';
        let amount: string = '';

        if (isIssuedCurrency(bid.TakerGets)) {
          amount = bid.TakerGets.value;
        } else {
          amount = bid.TakerGets;
        }
        openOrdersInMarket.set(bid.Sequence, {
          sequence: bid.Sequence,
          marketName: market.marketName,
          price: price,
          amount: amount,
          side: OrderSide.BUY,
        });
      }

      openOrders.set(market.marketName, openOrdersInMarket);
    }
    return openOrders;
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
