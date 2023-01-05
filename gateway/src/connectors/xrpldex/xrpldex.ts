import { XRPL } from '../../chains/xrpl/xrpl';
import {
  Client,
  OfferCancel,
  Transaction,
  xrpToDrops,
  AccountInfoResponse,
  BookOffersResponse,
  TxResponse,
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
  GetOpenOrdersResponse,
  OrderSide,
  GetOrdersResponse,
  GetOrderRequest,
} from './xrpldex.types';
import { promiseAllInBatches } from '../serum/serum.helpers';
import { isIssuedCurrency } from 'xrpl/dist/npm/models/transactions/common';

export type XRPLDEXish = XRPLDEX;

export class XRPLDEX {
  private static _instances: { [name: string]: XRPLDEX };
  private readonly _client: Client;
  private readonly _xrpl: XRPL;
  private _ready: boolean = false;

  initializing: boolean = false;
  chain: string;
  network: string;
  readonly connector: string = 'xrpldex';

  /**
   * Creates a new instance of xrplDEX.
   *
   * @param chain
   * @param network
   * @private
   */
  private constructor(chain: string, network: string) {
    this.chain = chain;
    this.network = network;

    this._xrpl = XRPL.getInstance(network);
    this._client = this._xrpl.client;
  }

  /**
   * Initialize the xrplDEX instance.
   *
   */
  async init() {
    if (!this._ready && !this.initializing) {
      this.initializing = true;

      if (!this._xrpl.ready()) {
        await this._xrpl.init();
      }

      if (!this._client.isConnected()) {
        await this._client.connect();
      }

      this._ready = true;
      this.initializing = false;
    }
  }

  public static getInstance(chain: string, network: string): XRPLDEX {
    if (XRPLDEX._instances === undefined) {
      XRPLDEX._instances = {};
    }
    if (!(network in XRPLDEX._instances)) {
      XRPLDEX._instances[network] = new XRPLDEX(chain, network);
    }

    return XRPLDEX._instances[network];
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

      if (!baseMarketResp)
        throw new MarketNotFoundError(`Market "${base}" not found.`);

      baseTickSize = baseMarketResp.result.account_data.TickSize ?? 15;
      const rawTransferRate =
        baseMarketResp.result.account_data.TransferRate ?? zeroTransferRate;
      baseTransferRate = rawTransferRate / zeroTransferRate - 1;
    } else {
      baseTickSize = 6;
      baseTransferRate = 0;
    }

    if (quoteCurrency != 'XRP') {
      const quoteMarketResp: AccountInfoResponse = await this._client.request({
        command: 'account_info',
        ledger_index: 'validated',
        account: quoteIssuer,
      });

      if (!quoteMarketResp)
        throw new MarketNotFoundError(`Market "${quote}" not found.`);

      quoteTickSize = quoteMarketResp.result.account_data.TickSize ?? 15;
      const rawTransferRate =
        quoteMarketResp.result.account_data.TransferRate ?? zeroTransferRate;
      quoteTransferRate = rawTransferRate / zeroTransferRate - 1;
    } else {
      quoteTickSize = 6;
      quoteTransferRate = 0;
    }

    const smallestTickSize = Math.min(baseTickSize, quoteTickSize);
    const minimumOrderSize = smallestTickSize;

    const result = {
      name: name,
      minimumOrderSize: minimumOrderSize,
      tickSize: smallestTickSize,
      baseTransferRate: baseTransferRate,
      quoteTransferRate: quoteTransferRate,
    };

    return result;
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

    await promiseAllInBatches(getMarket, names, 1, 1);

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

    const askQuality = asks.length > 0 ? asks[0].quality : undefined;
    const bidQuality = bids.length > 0 ? bids[0].quality : undefined;

    if (baseCurrency === 'XRP' || quoteCurrency === 'XRP') {
      topAsk = askQuality ? Number(askQuality) * 1000000 : 0;
      topBid = bidQuality ? (1 / Number(bidQuality)) * 1000000 : 0;
    } else {
      topAsk = askQuality ? Number(askQuality) : 0;
      topBid = bidQuality ? 1 / Number(bidQuality) : 0;
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

    await promiseAllInBatches(getTicker, marketNames, 1, 1);

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

    const askQuality = asks.length > 0 ? asks[0].quality : undefined;
    const bidQuality = bids.length > 0 ? bids[0].quality : undefined;

    if (baseCurrency === 'XRP' || quoteCurrency === 'XRP') {
      topAsk = askQuality ? Number(askQuality) * 1000000 : 0;
      topBid = bidQuality ? (1 / Number(bidQuality)) * 1000000 : 0;
    } else {
      topAsk = askQuality ? Number(askQuality) : 0;
      topBid = bidQuality ? 1 / Number(bidQuality) : 0;
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

    await promiseAllInBatches(getOrderBook, marketNames, 1, 1);

    return orderBooks;
  }

  async getOrders(orders: GetOrderRequest[]): Promise<GetOrdersResponse> {
    const queriedOrders: GetOrdersResponse = {};

    for (const order of orders) {
      const tx_resp: TxResponse = await this._client.request({
        command: 'tx',
        transaction: order.signature,
        binary: false,
      });

      const type = tx_resp.result.TransactionType;
      if (tx_resp.result.meta) {
        const meta: TransactionMetadata = tx_resp.result
          .meta as TransactionMetadata;
        const result = meta.TransactionResult;
        const prefix = result.slice(0, 3);

        switch (prefix) {
          case 'tec':
          case 'tef':
          case 'tel':
          case 'tem':
            queriedOrders[order.sequence] = {
              sequence: order.sequence,
              status: OrderStatus.FAILED,
              signature: order.signature,
              transactionResult: result,
            };
            continue;
        }

        if (type == 'OfferCreate') {
          if (result == 'tesSUCCESS') {
            queriedOrders[order.sequence] = {
              sequence: order.sequence,
              status: OrderStatus.OPEN,
              signature: order.signature,
              transactionResult: result,
            };
          } else {
            queriedOrders[order.sequence] = {
              sequence: order.sequence,
              status: OrderStatus.PENDING,
              signature: order.signature,
              transactionResult: result,
            };
          }
        } else if (type == 'OfferCancel') {
          if (result == 'tesSUCCESS') {
            queriedOrders[order.sequence] = {
              sequence: order.sequence,
              status: OrderStatus.CANCELED,
              signature: order.signature,
              transactionResult: result,
            };
          } else {
            queriedOrders[order.sequence] = {
              sequence: order.sequence,
              status: OrderStatus.PENDING,
              signature: order.signature,
              transactionResult: result,
            };
          }
        } else {
          queriedOrders[order.sequence] = {
            sequence: order.sequence,
            status: OrderStatus.UNKNOWN,
            signature: order.signature,
            transactionResult: result,
          };
        }
      } else {
        queriedOrders[order.sequence] = {
          sequence: order.sequence,
          status: OrderStatus.PENDING,
          signature: order.signature,
          transactionResult: 'pending',
        };
      }
    }

    const result = queriedOrders;
    return result;
  }

  async createOrder(order: CreateOrderRequest): Promise<CreateOrderResponse> {
    const [base, quote] = order.marketName.split('/');
    const [baseCurrency, baseIssuer] = base.split('.');
    const [quoteCurrency, quoteIssuer] = quote.split('.');

    const market = await this.getMarket(order.marketName);

    const xrpl = XRPL.getInstance(this.network);
    const wallet = await xrpl.getWallet(order.walletAddress);
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
        currency: quoteCurrency,
        issuer: quoteIssuer,
        value: Number(total.toPrecision(market.tickSize)).toString(),
      };
      we_get = {
        currency: baseCurrency,
        issuer: baseIssuer,
        value: Number(order.amount.toPrecision(market.tickSize)).toString(),
      };

      fee = market.baseTransferRate;
    } else {
      we_pay = {
        currency: baseCurrency,
        issuer: baseIssuer,
        value: Number(order.amount.toPrecision(market.tickSize)).toString(),
      };
      we_get = {
        currency: quoteCurrency,
        issuer: quoteIssuer,
        value: Number(total.toPrecision(market.tickSize)).toString(),
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
      TakerGets: we_pay.currency == 'XRP' ? we_pay.value : we_pay,
      TakerPays: we_get.currency == 'XRP' ? we_get.value : we_get,
    };

    if (order.sequence != undefined) {
      offer.OfferSequence = order.sequence;
    }

    const prepared = await this._client.autofill(offer);
    const signed = wallet.sign(prepared);
    const response = await this._client.submit(signed.tx_blob);

    const orderStatus = OrderStatus.PENDING;
    // const orderSequence = -1;
    // const orderLedgerIndex = '';

    // if (response.result) {
    //   const meta = response.result.meta;
    //   if (meta) {
    //     const affectedNodes = (meta as TransactionMetadata).AffectedNodes;

    //     for (const affnode of affectedNodes) {
    //       if ('ModifiedNode' in affnode) {
    //         if (affnode.ModifiedNode.LedgerEntryType == 'Offer') {
    //           // Usually a ModifiedNode of type Offer indicates a previous Offer that
    //           // was partially consumed by this one.
    //           orderStatus = OrderStatus.PARTIALLY_FILLED;
    //         }
    //       } else if ('DeletedNode' in affnode) {
    //         if (affnode.DeletedNode.LedgerEntryType == 'Offer') {
    //           // The removed Offer may have been fully consumed, or it may have been
    //           // found to be expired or unfunded.
    //           // TODO: Make a seperate method for cancelling orders
    //           if (offer.OfferSequence == undefined) {
    //             orderStatus = OrderStatus.FILLED;
    //           }
    //         }
    //       } else if ('CreatedNode' in affnode) {
    //         if (affnode.CreatedNode.LedgerEntryType == 'Offer') {
    //           // Created an Offer object on the Ledger
    //           orderStatus = OrderStatus.OPEN;
    //           orderSequence = response.result.Sequence ?? -1;
    //           orderLedgerIndex = affnode.CreatedNode.LedgerIndex;
    //         }
    //       }
    //     }
    //   }
    // }

    const returnResponse: CreateOrderResponse = {
      walletAddress: order.walletAddress,
      marketName: order.marketName,
      price: order.price,
      amount: order.amount,
      side: order.side,
      type: order.type,
      fee,
      orderLedgerIndex: response.result.validated_ledger_index.toString(),
      status: orderStatus,
      sequence: response.result.tx_json.Sequence ?? -1,
      signature: response.result.tx_json.hash,
    };

    return returnResponse;
  }

  async createOrders(
    orders: CreateOrderRequest[],
    waitUntilIncludedInBlock: boolean
  ): Promise<Record<number, CreateOrderResponse>> {
    const createdOrders: Record<number, CreateOrderResponse> = {};

    if (orders.length <= 0) {
      return createdOrders;
    }

    const getCreatedOrders = async (
      order: CreateOrderRequest
    ): Promise<void> => {
      const createdOrder = await this.createOrder(order);

      createdOrders[createdOrder.sequence] = createdOrder;
    };

    await promiseAllInBatches(getCreatedOrders, orders, 1, 1);

    if (waitUntilIncludedInBlock) {
      const queriedOrders: GetOrderRequest[] = [];
      let pooling = true;
      let transactionStatuses: GetOrdersResponse;

      for (const key in createdOrders) {
        const sequence = parseInt(key);
        const signature = createdOrders[key].signature;

        if (signature != undefined) {
          queriedOrders.push({
            sequence,
            signature,
          });
        }
      }

      while (pooling) {
        transactionStatuses = await this.getOrders(queriedOrders);

        for (const key in transactionStatuses) {
          if (transactionStatuses[key]['status'] == OrderStatus.PENDING) {
            pooling = true;
            await new Promise((resolve) => setTimeout(resolve, 5000));
            break;
          }

          createdOrders[key]['status'] = transactionStatuses[key]['status'];
          createdOrders[key]['transactionResult'] =
            transactionStatuses[key]['transactionResult'];

          pooling = false;
        }
      }
    }

    return createdOrders;
  }

  async cancelOrder(order: CancelOrderRequest): Promise<CancelOrderResponse> {
    const xrpl = XRPL.getInstance(this.network);
    const wallet = await xrpl.getWallet(order.walletAddress);
    const request: OfferCancel = {
      TransactionType: 'OfferCancel',
      Account: wallet.classicAddress,
      OfferSequence: order.offerSequence,
    };

    const prepared = await this._client.autofill(request);
    const signed = wallet.sign(prepared);
    const response = await this._client.submit(signed.tx_blob);

    const orderStatus = OrderStatus.PENDING;

    // if (response.result) {
    //   const meta = response.result.meta;
    //   if (meta) {
    //     const affectedNodes = (meta as TransactionMetadata).AffectedNodes;

    //     for (const affnode of affectedNodes) {
    //       if ('DeletedNode' in affnode) {
    //         if (affnode.DeletedNode.LedgerEntryType == 'Offer') {
    //           orderStatus = OrderStatus.CANCELED;
    //         }
    //       }
    //     }
    //   }
    // }

    const returnResponse: CancelOrderResponse = {
      walletAddress: order.walletAddress,
      status: orderStatus,
      signature: response.result.tx_json.hash,
    };

    return returnResponse;
  }

  async cancelOrders(
    orders: CancelOrderRequest[],
    waitUntilIncludedInBlock: boolean
  ): Promise<Record<number, CancelOrderResponse>> {
    const cancelledOrders: Record<number, CancelOrderResponse> = {};

    if (orders.length <= 0) {
      return cancelledOrders;
    }

    const getCancelledOrders = async (
      order: CancelOrderRequest
    ): Promise<void> => {
      const cancelledOrder = await this.cancelOrder(order);

      cancelledOrders[order.offerSequence] = cancelledOrder;
    };

    await promiseAllInBatches(getCancelledOrders, orders, 1, 1);

    if (waitUntilIncludedInBlock) {
      const queriedOrders: GetOrderRequest[] = [];
      let pooling = true;
      let transactionStatuses: GetOrdersResponse;

      for (const key in cancelledOrders) {
        const sequence = parseInt(key);
        const signature = cancelledOrders[key].signature;

        if (signature != undefined) {
          queriedOrders.push({
            sequence,
            signature,
          });
        }
      }

      while (pooling) {
        transactionStatuses = await this.getOrders(queriedOrders);

        for (const key in transactionStatuses) {
          if (transactionStatuses[key]['status'] == OrderStatus.PENDING) {
            pooling = true;
            await new Promise((resolve) => setTimeout(resolve, 5000));
            break;
          }

          cancelledOrders[key]['status'] = transactionStatuses[key]['status'];
          cancelledOrders[key]['transactionResult'] =
            transactionStatuses[key]['transactionResult'];

          pooling = false;
        }
      }
    }

    return cancelledOrders;
  }

  async getOpenOrders(params: {
    market?: GetOpenOrderRequest;
    markets?: GetOpenOrderRequest[];
  }): Promise<GetOpenOrdersResponse> {
    const openOrders: any = {};

    let marketArray: GetOpenOrderRequest[] = [];
    if (params.market) marketArray.push(params.market);
    if (params.markets) {
      marketArray = marketArray.concat(params.markets);
    }

    for (const market of marketArray) {
      const [base, quote] = market.marketName.split('/');

      const [baseCurrency, baseIssuer] = base.split('.');
      const [quoteCurrency, quoteIssuer] = quote.split('.');

      const openOrdersInMarket: any = {};

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

      let asks = orderbook_resp_ask.result.offers;
      let bids = orderbook_resp_bid.result.offers;

      asks = asks.filter((ask) => ask.Account == market.walletAddress);
      bids = bids.filter((bid) => bid.Account == market.walletAddress);

      for (const ask of asks) {
        const price = ask.quality ?? '-1';
        let amount: string = '';

        if (isIssuedCurrency(ask.TakerGets)) {
          amount = ask.TakerGets.value;
        } else {
          amount = ask.TakerGets;
        }

        openOrdersInMarket[String(ask.Sequence)] = {
          sequence: ask.Sequence,
          marketName: market.marketName,
          price: price,
          amount: amount,
          side: OrderSide.SELL,
        };
      }

      for (const bid of bids) {
        const price = Math.pow(Number(bid.quality), -1).toString() ?? '-1';
        let amount: string = '';

        if (isIssuedCurrency(bid.TakerGets)) {
          amount = bid.TakerGets.value;
        } else {
          amount = bid.TakerGets;
        }

        openOrdersInMarket[String(bid.Sequence)] = {
          sequence: bid.Sequence,
          marketName: market.marketName,
          price: price,
          amount: amount,
          side: OrderSide.BUY,
        };
      }

      openOrders[market.marketName] = openOrdersInMarket;
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
