import { Account, Connection, PublicKey } from '@solana/web3.js';
import {
  Market as SerumMarket,
  Orderbook as SerumOrderBook,
  MARKETS,
} from '@project-serum/serum';
import { Solana } from '../../chains/solana/solana';
import { SerumConfig } from './serum.config';
import { Market, Order, OrderBook, CreateOrder, Ticker, GetOrder, CancelOrder } from './serum.types';
import BN from 'bn.js';
import {
  OrderParams as SerumOrderParams,
  Order as SerumOrder, OpenOrders,
} from '@project-serum/serum/lib/market';
import { OrderSide } from '../../clob/clob.types';

import { Cache, CacheContainer } from 'node-ts-cache'
import { MemoryStorage } from 'node-ts-cache-storage-memory'

const caches = {
  instances: new CacheContainer(new MemoryStorage()),

  market: new CacheContainer(new MemoryStorage()),
  markets: new CacheContainer(new MemoryStorage()),
  allMarkets: new CacheContainer(new MemoryStorage()),

  orderBook: new CacheContainer(new MemoryStorage()),
  orderBooks: new CacheContainer(new MemoryStorage()),
  allOrderBooks: new CacheContainer(new MemoryStorage()),

  ticker: new CacheContainer(new MemoryStorage()),
  tickers: new CacheContainer(new MemoryStorage()),
  allTickers: new CacheContainer(new MemoryStorage()),

  order: new CacheContainer(new MemoryStorage()),
  orders: new CacheContainer(new MemoryStorage()),
  allOrders: new CacheContainer(new MemoryStorage()),

  filledOrder: new CacheContainer(new MemoryStorage()),
  filledOrders: new CacheContainer(new MemoryStorage()),
  allFilledOrders: new CacheContainer(new MemoryStorage()),
}

export type Serumish = Serum;

export class Serum {
  private initializing: boolean = false;

  private readonly config: SerumConfig.Config;
  private solana!: Solana;
  private readonly connection: Connection;

  ready: boolean = false;
  chain: string;
  network: string;

  /**
   *
   * @param chain
   * @param config
   */
  private constructor(chain: string, network: string) {
    this.chain = chain;
    this.network = network;

    this.config = SerumConfig.config;

    this.connection = new Connection(this.config.network.rpcUrl);
  }

  /**
   * Get the Serum instance for the given chain and network
   *
   * @param chain
   * @param network
   */
  @Cache(caches.instances, {isCachedForever = true})
  static async getInstance(chain: string, network: string): Promise<Serum> {
    const instance = new Serum(chain, network);

    await instance.init();

    return instance;
  }

  private parseToMarket(
    info: Record<string, unknown>,
    market: SerumMarket
  ): Market {
    return {
      ...info,
      market: market,
    } as Market;
  }

  private parseToOrderBook(
    asks: SerumOrderBook,
    bids: SerumOrderBook
  ): OrderBook {
    return {
      asks: this.parseToOrders(asks),
      bids: this.parseToOrders(bids),
      orderBook: {
        asks: asks,
        bids: bids,
      },
    } as OrderBook;
  }

  private parseToOrder(order: SerumOrder | Record<string, unknown>): Order {
    // TODO convert the loadFills and placeOrder returns too!!!
    // TODO return the clientOrderId and status pending when creating a new order (the exchangeOrderId will not be sent)!!!
    return {
      ...order,
      order: order,
    } as Order;
  }

  private parseToOrders(
    orders: SerumOrder[] | SerumOrderBook | any[]
  ): Order[] {
    const result = [];

    for (const order of orders) {
      result.push(this.parseToOrder(order));
    }

    return result;
  }

  private parseToTicker(ticker: any): Ticker {
    return {
      ...ticker,
      ticker: ticker,
    } as Ticker;
  }

  /**
   * Initialize the Serum instance.
   */
  async init() {
    if (!this.ready && !this.initializing) {
      this.initializing = true;

      this.solana = Solana.getInstance(this.network);
      await this.solana.init();

      await this.getAllMarkets();

      this.ready = true;
      this.initializing = false;
    }
  }

  /**
   *
   * @param name
   */
  @Cache(caches.market, {isCachedForever = true})
  async getMarket(name: string): Promise<Market> {
    const markets = await this.getAllMarkets();

    const market = markets.get(name);

    if (!market) throw new Error(`Market ${name} not found.`);

    return market;
  }

  /**
   *
   * @param names
   */
  @Cache(caches.markets, {isCachedForever = true})
  async getMarkets(names: string[]): Promise<Map<string, Market>> {
    const markets = new Map<string, Market>();

    for (const name of names) {
      const market = await this.getMarket(name);

      markets.set(name, market);
    }

    return markets;
  }

  /**
   *
   */
  @Cache(caches.allMarkets, {isCachedForever = true})
  async getAllMarkets(): Promise<Map<string, Market>> {
    const allMarkets = new Map<string, Market>();

    for (const market of MARKETS) {
      allMarkets.set(
        market.name,
        this.parseToMarket(
          market,
          await SerumMarket.load(
            this.connection,
            market.address,
            {},
            market.programId
          )
        )
      );
    }

    return allMarkets;
  }

  @Cache(caches.orderBook, {ttl: 1})
  async getOrderBook(marketName: string): Promise<OrderBook> {
    const market = await this.getMarket(marketName);

    if (!market) throw new Error(`Market ${marketName} not found.`);

    return this.parseToOrderBook(
      await market.market.loadAsks(this.connection),
      await market.market.loadBids(this.connection)
    );
  }

  @Cache(caches.orderBooks, {ttl: 1})
  async getOrderBooks(
    marketNames: string[]
  ): Promise<Map<string, OrderBook>> {
    const orderBooks = new Map<string, OrderBook>();

    for (const marketName of marketNames) {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    return orderBooks;
  }

  @Cache(caches.allOrderBooks, {ttl: 1})
  async getAllOrderBooks(): Promise<Map<string, OrderBook>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.getOrderBooks(marketNames);
  }

  @Cache(caches.ticker, {ttl: 1})
  async getTicker(marketName: string): Promise<Ticker> {
    const market = await this.getMarket(marketName);

    if (!market) throw new Error(`Market ${marketName} not found.`);

    return this.parseToTicker(market.market.loadTicker(this.connection));
  }

  @Cache(caches.tickers, {ttl: 1})
  async getTickers(marketNames: string[]): Promise<Map<string, Ticker>> {
    const tickers = new Map<string, Ticker>();

    for (const marketName of marketNames) {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    }

    return tickers;
  }

  @Cache(caches.allTickers, {ttl: 1})
  async getAllTickers(): Promise<Map<string, Ticker>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getTickers(marketNames);
  }

  @Cache(caches.order, {ttl: 1})
  async getOrder(target: GetOrder): Promise<Order> {
    const market = await this.getMarket(target.marketName);

    if (!market) throw new Error(`Market ${target.marketName} not found.`);

    return this.parseToOrder(
      await market.market.loadOrder(this.connection, target.clientOrderId, target.exchangeOrderId)
    );
  }

  @Cache(caches.orders, {ttl: 1})
  async getOrders(targets: GetOrder[]): Promise<Map<BN, Order>> {
    const orders = new Map<BN, Order>();

    for (const target of targets) {
      const order = await this.getOrder(target);

      orders.set(order.id, order);
    }

    return orders;
  }

  async getAllOpenOrdersForMarket(target: OpenOrders): Promise<Order[]> {
    const market = await this.getMarket(target.marketName);

    if (!market) throw Error(`Market ${target.marketName} not found.`);

    const owner = await this.solana.getAccount(target.address);

    const serumOpenOrders = await market.market.loadOrdersForOwner(
      this.connection,
      owner.publicKey
    );

    return this.parseToOrders(serumOpenOrders);
  }

  async getAllOpenOrdersForMarkets(target: OpenOrders): Promise<Map<string, Order[]>> {
    const result = new Map<string, Order[]>();

    const markets = await this.getMarkets(target.marketNames);

    for (const [marketName, market] of markets) {
      result.set(marketName, await this.getAllOpenOrdersForMarket(market));
    }

    return result;
  }

  async getAllOpenOrders(): Promise<Map<string, Order[]>> {
    return await this.getAllOpenOrdersForMarkets(this.getAllMarkets());
  }

  async createOrder(candidate: CreateOrder): Promise<Order> {
    const market = await this.getMarket(candidate.marketName);

    if (!market)
      throw new Error(`Market ${candidate.marketName} not found.`);

    const owner = await this.solana.getAccount(candidate.address);

    let mintAddress: PublicKey;
    if (candidate.side == OrderSide.BUY.toLowerCase()) {
      mintAddress = market.market.quoteMintAddress;
    } else {
      mintAddress = market.market.baseMintAddress;
    }

    const serumOrderParams: SerumOrderParams<Account> = {
      ...candidate,
      owner: owner,
      payer: await this.solana.findAssociatedTokenAddress(
        owner.publicKey,
        mintAddress
      ),
    };

    const signature = await market.market.placeOrder(
      this.connection,
      serumOrderParams
    );

    return this.parseToOrder({
      ...candidate,
      signature: signature,
    });
  }

  async createOrders(candidates: CreateOrder[]): Promise<Order[]> {
    // TODO what about if some orders fail to be created? Is it possible to create transactions with Serum?!!!
    const createdOrders = [];
    for (const candidateOrder of candidates) {
      const order = await this.createOrder(candidateOrder);

      createdOrders.push(order);
    }

    return createdOrders;
  }

  async cancelOrder(request: CancelOrder): Promise<any> {
    const market = await this.getMarket(request.marketName);

    if (!market) throw Error(`Market ${request.marketName} not found.`);

    const owner = await this.solana.getAccount(request.address);
    const order = await this.getOrder(request.order);

    await market.market.cancelOrder(this.connection, owner, order?.order);
  }

  async cancelOrders(orders: Order[]): Promise<Order[]> {
    // TODO what about if some orders fail to be canceled? Is it possible to create transactions with Serum?!!!
    const canceledOrders = [];

    for (const order of orders) {
      const result = await this.cancelOrder(order);

      canceledOrders.push(result);
    }

    return canceledOrders;
  }

  async cancelAllOpenOrders(): Promise<Order[]> {
    const orders = await this.getAllOpenOrders();

    return await this.cancelOrders(orders);
  }

  @Cache(caches.filledOrder, {ttl: 60})
  async getFilledOrder(): Promise<Order | undefined> {
    for (market )
  }

  @Cache(caches.filledOrders, {ttl: 60})
  async getFilledOrders(
    marketNames?: string | string[]
  ): Promise<Map<string, Order[] | undefined> | undefined> {
    let markets: Map<string, Market | undefined>;

    if (!marketNames) {
      markets = await this.getAllMarkets();
    } else if (typeof marketNames === 'string') {
      markets = await this.getMarkets([marketNames]);
    } else {
      markets = await this.getMarkets(marketNames);
    }

    if (!markets || !markets.size) return;

    const result = new Map<string, Order[] | undefined>();

    for (const [marketName, market] of markets) {
      const orders = await market?.market.loadFills(this.connection);

      if (orders) result.set(marketName, this.parseToOrders(orders));
      else result.set(marketName, undefined);
    }

    return result;
  }

  @Cache(caches.allFilledOrders, {ttl: 60})
  async getAllFilledOrders(): Promise<
    Map<string, Order[] | undefined> | undefined
  > {
    return this.getFilledOrders();
  }
}
