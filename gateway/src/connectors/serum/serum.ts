import { Account, Connection, PublicKey } from '@solana/web3.js';
import {
  Market as SerumMarket,
  MARKETS,
  Orderbook as SerumOrderBook,
} from '@project-serum/serum';
import { Solana } from '../../chains/solana/solana';
import { SerumConfig } from './serum.config';
import {
  CreateOrder,
  OrderRequest,
  Market,
  Order,
  OrderBook,
  Ticker,
  OrderRequests,
} from './serum.types';
import {
  Order as SerumOrder,
  OrderParams as SerumOrderParams,
} from '@project-serum/serum/lib/market';
import { OrderSide } from '../../clob/clob.types';

import { Cache, CacheContainer } from 'node-ts-cache';
import { MemoryStorage } from 'node-ts-cache-storage-memory';

const caches = {
  instances: new CacheContainer(new MemoryStorage()),

  market: new CacheContainer(new MemoryStorage()),
  markets: new CacheContainer(new MemoryStorage()),
  allMarkets: new CacheContainer(new MemoryStorage()),
};

export type Serumish = Serum;

// TODO create a documentation saying how many requests we are sending through the Solana/Serum connection
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
  @Cache(caches.instances, { isCachedForever: true })
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
  @Cache(caches.market, { isCachedForever: true })
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
  @Cache(caches.markets, { ttl: 60 * 60 })
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
  @Cache(caches.allMarkets, { ttl: 60 * 60 })
  async getAllMarkets(): Promise<Map<string, Market>> {
    const allMarkets = new Map<string, Market>();

    // TODO use fetch to retrieve the markets instead of using the JSON!!!

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

  async getOrderBook(marketName: string): Promise<OrderBook> {
    const market = await this.getMarket(marketName);

    if (!market) throw new Error(`Market ${marketName} not found.`);

    return this.parseToOrderBook(
      await market.market.loadAsks(this.connection),
      await market.market.loadBids(this.connection)
    );
  }

  async getOrderBooks(marketNames: string[]): Promise<Map<string, OrderBook>> {
    const orderBooks = new Map<string, OrderBook>();

    for (const marketName of marketNames) {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    return orderBooks;
  }

  async getAllOrderBooks(): Promise<Map<string, OrderBook>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.getOrderBooks(marketNames);
  }

  async getTicker(marketName: string): Promise<Ticker> {
    const market = await this.getMarket(marketName);

    if (!market) throw new Error(`Market ${marketName} not found.`);

    // TODO check the returned order of loadFills!!!
    return this.parseToTicker(
      (await market.market.loadFills(this.connection, 1))[0]
    );
  }

  async getTickers(marketNames: string[]): Promise<Map<string, Ticker>> {
    const tickers = new Map<string, Ticker>();

    for (const marketName of marketNames) {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    }

    return tickers;
  }

  async getAllTickers(): Promise<Map<string, Ticker>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getTickers(marketNames);
  }

  async getOrder(target: {
    marketName: string;
    clientOrderId: string;
    exchangeOrderId: string;
    address: string;
  }): Promise<Order> {
    const market = await this.getMarket(target.marketName);

    if (!market) throw new Error(`Market ${target.marketName} not found.`);

    const openOrders = await this.getAllOpenOrders(target.address);
    for (const openOrdersForMarket of openOrders.values()) {
      const order = openOrdersForMarket.find(
        (order) =>
          order.id === target.clientOrderId ||
          order.exchangeId === target.exchangeOrderId
      );

      if (order) return order;
    }

    const filledOrders = await this.getAllFilledOrders();
    for (const filledOrdersForMarket of filledOrders?.values()) {
      const order = filledOrdersForMarket.find(
        (order) => order.id === target.clientOrderId
      );

      if (order) return order;
    }

    throw Error(`Order ${target.clientOrderId} not found.`);
  }

  async getOrders(targets: OrderRequest[]): Promise<Map<string, Order>> {
    const orders = new Map<string, Order>();

    for (const target of targets) {
      const order = await this.getOrder(target);

      orders.set(order.id, order);
    }

    return orders;
  }

  async getAllOpenOrdersForMarket(
    marketName: string,
    address: string
  ): Promise<Order[]> {
    const market = await this.getMarket(marketName);

    if (!market) throw Error(`Market ${marketName} not found.`);

    const owner = await this.solana.getAccount(address);

    const serumOpenOrders = await market.market.loadOrdersForOwner(
      this.connection,
      owner.publicKey
    );

    return this.parseToOrders(serumOpenOrders);
  }

  async getAllOpenOrdersForMarkets(
    marketNames: string[],
    address: string
  ): Promise<Map<string, Order[]>> {
    const result = new Map<string, Order[]>();

    for (const marketName of marketNames) {
      result.set(
        marketName,
        await this.getAllOpenOrdersForMarket(marketName, address)
      );
    }

    return result;
  }

  async getAllOpenOrders(address: string): Promise<Map<string, Order[]>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getAllOpenOrdersForMarkets(marketNames, address);
  }

  async createOrder(candidate: CreateOrder): Promise<Order> {
    const market = await this.getMarket(candidate.marketName);

    if (!market) throw new Error(`Market ${candidate.marketName} not found.`);

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
    // TODO improve to use transactions in the future

    const createdOrders = [];
    for (const candidateOrder of candidates) {
      const order = await this.createOrder(candidateOrder);

      createdOrders.push(order);
    }

    return createdOrders;
  }

  async cancelOrder(target: OrderRequest): Promise<any> {
    const market = await this.getMarket(target.marketName);

    if (!market) throw Error(`Market ${target.marketName} not found.`);

    const owner = await this.solana.getAccount(target.address);

    const order = await this.getOrder({
      marketName: target.marketName,
      clientOrderId: target.clientOrderId,
      exchangeOrderId: target.exchangeOrderId,
      address: target.address,
    });

    await market.market.cancelOrder(this.connection, owner, order.order);
  }

  async cancelOrders(targets: OrderRequest[]): Promise<Order[]> {
    // TODO improve to use transactions in the future

    const canceledOrders = [];

    for (const target of targets) {
      const result = await this.cancelOrder({
        marketName: target.marketName,
        address: target.address,
        clientOrderId: target.clientOrderId,
        exchangeOrderId: target.exchangeOrderId,
      });

      canceledOrders.push(result);
    }

    return canceledOrders;
  }

  async cancelAllOpenOrders(address: string): Promise<Order[]> {
    const map = await this.getAllOpenOrders(address);

    const orders = [] as Order[];

    for (const orders of map.values()) {
      await this.cancelOrders(
        orders.map((order) => {
          return {
            marketName: order.marketName,
            address: order.ownerAddress,
            clientOrderId: order.id,
            exchangeOrderId: order.exchangeId,
          };
        })
      );

      orders.push(...orders);
    }

    return orders;
  }

  async getFilledOrder(target: OrderRequest): Promise<Order> {
    const filledOrders = await this.getFilledOrders([
      {
        marketName: target.marketName,
        addresses: target.address ? [target.address] : [],
        exchangeOrderIds: target.exchangeOrderId
          ? [target.exchangeOrderId]
          : [],
        clientOrderIds: target.clientOrderId ? [target.clientOrderId] : [],
      },
    ]);

    return filledOrders.values().next().value;
  }

  async getFilledOrders(
    targets: OrderRequests[]
  ): Promise<Map<string, Order[]>> {
    const result = new Map<string, Order[]>();

    for (const target of targets) {
      let marketsMap = new Map<string, Market>();

      if (!target.marketName) {
        marketsMap = await this.getAllMarkets();
      } else {
        marketsMap.set(
          target.marketName,
          await this.getMarket(target.marketName)
        );
      }

      for (const [marketName, market] of marketsMap) {
        // TODO will not work properly because we are loading the fills for everyone and not just for the owner orders!!!
        // TODO check if -1 would also work!!!
        const orders = await market.market.loadFills(this.connection, 0);

        result.set(marketName, this.parseToOrders(orders));
      }
    }

    return result;
  }

  async getAllFilledOrders(): Promise<Map<string, Order[]>> {
    return await this.getFilledOrders([{}]);
  }
}
