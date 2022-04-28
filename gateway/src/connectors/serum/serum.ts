import {Account, Connection, PublicKey} from '@solana/web3.js';
import {Market as SerumMarket, MARKETS, Orderbook as SerumOrderBook,} from '@project-serum/serum';
import axios from 'axios';
import {Solana} from '../../chains/solana/solana';
import {getSerumConfig, SerumConfig} from './serum.config';
import {
  CancelOrderRequest,
  CancelOrdersRequest,
  CreateOrdersRequest,
  GetFilledOrderRequest,
  GetFilledOrdersRequest,
  GetOpenOrderRequest,
  GetOpenOrdersRequest,
  GetOrderRequest,
  GetOrdersRequest,
  IMap,
  Market,
  MarketNotFoundError,
  Order,
  OrderBook,
  OrderNotFoundError,
  OrderStatus,
  BasicSerumMarket,
  Ticker,
  TickerNotFoundError,
} from './serum.types';
import {Order as SerumOrder, OrderParams as SerumOrderParams,} from '@project-serum/serum/lib/market';

import {Cache, CacheContainer} from 'node-ts-cache';
import {MemoryStorage} from 'node-ts-cache-storage-memory';
import BN from "bn.js";
import {
  convertFilledOrderToTicker,
  convertOrderSideToSerumSide,
  convertOrderTypeToSerumType,
  convertSerumMarketToMarket,
  convertSerumOrderToOrder
} from "./serum.convertors";
import {sleep} from "@blockworks-foundation/mango-client";

const caches = {
  instances: new CacheContainer(new MemoryStorage()),

  market: new CacheContainer(new MemoryStorage()),
  markets: new CacheContainer(new MemoryStorage()),
  allMarkets: new CacheContainer(new MemoryStorage()),
};

export type Serumish = Serum;

/**
 * Same as Promise.all(items.map(item => task(item))), but it waits for
 * the first {batchSize} promises to finish before starting the next batch.
 *
 * @template A
 * @template B
 * @param {function(A): B} task The task to run for each item.
 * @param {A[]} items Arguments to pass to the task for each call.
 * @param {int} batchSize
 * @returns {B[]}
 */
export const promiseAllInBatches = async (task: any, items: any[], batchSize: number, delay: number = 0): Promise<any[]> =>{
    let position = 0;
    let results: any[] = [];
    while (position < items.length) {
        const itemsForBatch = items.slice(position, position + batchSize);
        results = [...results, ...await Promise.all(itemsForBatch.map(item => task(item)))];
        sleep(delay);
        position += batchSize;
    }
    return results;
}

// TODO create a documentation saying how many requests we are sending through the Solana/Serum connection!!!
export class Serum {
  private initializing: boolean = false;

  private readonly config: SerumConfig.Config;
  private solana!: Solana;
  private readonly connection: Connection;
  private _ready: boolean = false;

  chain: string;
  network: string;
  readonly connector: string = 'serum';

  /**
   *
   * @param chain
   * @param config
   */
  private constructor(chain: string, network: string) {
    this.chain = chain;
    this.network = network;

    this.config = getSerumConfig(network)

    this.connection = new Connection(this.config.network.rpcURL);
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

  private parseToOrderBook(
    market: Market,
    asks: SerumOrderBook,
    bids: SerumOrderBook
  ): OrderBook {
    return {
      market: market,
      asks: this.parseToMapOfOrders(market, asks, undefined),
      bids: this.parseToMapOfOrders(market, bids, undefined),
      orderBook: {
        asks: asks,
        bids: bids,
      },
    } as OrderBook;
  }

  private parseToMapOfOrders(
    market: Market,
    orders: SerumOrder[] | SerumOrderBook | any[],
    address?: string
  ): IMap<string, Order> {
    const result = IMap<string, Order>().asMutable();

    for (const order of orders) {
      result.set(
        order.orderId,
        convertSerumOrderToOrder(
          market,
          order,
          undefined,
          undefined,
          address
        )
      );
    }

    return result;
  }

  /**
   * Initialize the Serum instance.
   */
  async init() {
    if (!this._ready && !this.initializing) {
      this.initializing = true;

      this.solana = await Solana.getInstance(this.network);
      await this.solana.init();

      await this.getAllMarkets();

      this._ready = true;
      this.initializing = false;
    }
  }

  ready(): boolean {
    return this._ready;
  }

  // TODO remove this accessor!!!
  getConnection(): Connection {
    return this.connection;
  }

  /**
   *
   * @param name
   */
  // @Cache(caches.market, { isCachedForever: true })
  async getMarket(name?: string): Promise<Market> {
    if (!name) throw new MarketNotFoundError(`No market informed.`);

    const markets = await this.getAllMarkets();

    // TODO Change to load the market directly instead of using the map for performance reasons!!!
    const market = markets.get(name);

    if (!market) throw new MarketNotFoundError(`Market "${name}" not found.`);

    return market;
  }

  /**
   *
   * @param names
   */
  // @Cache(caches.markets, { ttl: 60 * 60 })
  async getMarkets(names: string[]): Promise<IMap<string, Market>> {
    const markets = IMap<string, Market>().asMutable();

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
  async getAllMarkets(): Promise<IMap<string, Market>> {
    const allMarkets = IMap<string, Market>().asMutable();

    const marketsURL =
      this.config.marketsURL
      || 'https://raw.githubusercontent.com/project-serum/serum-ts/master/packages/serum/src/markets.json';

    let marketsInformation: BasicSerumMarket[];

    try {
      marketsInformation = (await axios.get(marketsURL)).data;
    } catch (e) {
      marketsInformation = MARKETS;
    }

    // TODO Start using the https://www.npmjs.com/package/decimal library!!!

    const loadMarket = async(market: BasicSerumMarket): Promise<void> => {
      const serumMarket = await SerumMarket.load(
        this.connection,
        new PublicKey(market.address),
        {},
        new PublicKey(market.programId)
      );

      allMarkets.set(
        market.name,
        convertSerumMarketToMarket(
          serumMarket,
          market
        )
      );
    }

    await promiseAllInBatches(loadMarket, marketsInformation, 100, 1500);

    return allMarkets;
  }

  async getOrderBook(marketName: string): Promise<OrderBook> {
    const market = await this.getMarket(marketName);

    const asks = await market.market.loadAsks(this.connection);
    const bids = await market.market.loadBids(this.connection);

    return this.parseToOrderBook(
      market,
      asks,
      bids
    );
  }

  async getOrderBooks(marketNames: string[]): Promise<IMap<string, OrderBook>> {
    const orderBooks = IMap<string, OrderBook>().asMutable();

    for (const marketName of marketNames) {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    return orderBooks;
  }

  async getAllOrderBooks(): Promise<IMap<string, OrderBook>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.getOrderBooks(marketNames);
  }

  async getTicker(marketName: string): Promise<Ticker> {
    const market = await this.getMarket(marketName);

    // TODO change the mechanism to retrieve ticker information, this approach is not always available!!!
    const filledOrders = await market.market.loadFills(this.connection);
    if (!filledOrders || !filledOrders.length)
      throw new TickerNotFoundError(`Ticker data is currently not available for market "${marketName}".`);

    const mostRecentFilledOrder = filledOrders[0];

    return convertFilledOrderToTicker(Date.now(), mostRecentFilledOrder);
  }

  async getTickers(marketNames: string[]): Promise<IMap<string, Ticker>> {
    const tickers = IMap<string, Ticker>().asMutable();

    for (const marketName of marketNames) {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    }

    return tickers;
  }

  async getAllTickers(): Promise<IMap<string, Ticker>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getTickers(marketNames);
  }

  async getOpenOrder(target: GetOpenOrderRequest): Promise<Order> {
    if (!target.id && !target.exchangeId)
      throw new OrderNotFoundError('No client id or exchange id provided.');

    if (!target.ownerAddress)
      throw new OrderNotFoundError(`No owner address provided for order "${target.id} / ${target.exchangeId}".`);

    const mapOfOpenOrdersForMarkets = await this.getAllOpenOrders(
      target.ownerAddress
    );
    for (const mapOfOpenOrdersForMarket of mapOfOpenOrdersForMarkets.values()) {
      for (const openOrder of mapOfOpenOrdersForMarket.values()) {
        if (
          openOrder.id === target.id ||
          openOrder.exchangeId === target.exchangeId
        ) {
          return openOrder;
        }
      }
    }

    throw new OrderNotFoundError(`Order ${target.id} not found.`);
  }

  async getFilledOrder(target: GetFilledOrderRequest): Promise<Order> {
    if (!target.id && !target.exchangeId)
      throw new OrderNotFoundError('No client id or exchange id provided.');

    const mapOfFilledOrders = await this.getAllFilledOrders();
    for (const filledOrder of mapOfFilledOrders.values()) {
      if (
        filledOrder.id === target.id ||
        filledOrder.exchangeId === target.exchangeId
      ) {
        return filledOrder;
      }
    }

    throw new OrderNotFoundError(`Order "${target.id}" not found.`);
  }

  async getOrder(target: GetOrderRequest): Promise<Order> {
    if (!target.id && !target.exchangeId)
      throw new OrderNotFoundError('No client id or exchange id provided.');

    try {
      return await this.getOpenOrder(target);
    } catch (exception) {
      if (exception instanceof OrderNotFoundError) {
        return await this.getFilledOrder(target);
      }

      throw exception;
    }
  }

  async getOrders(targets: GetOrdersRequest[]): Promise<IMap<string, Order>> {
    const orders = IMap<string, Order>().asMutable();
    const temporary = IMap<string, Order>().asMutable();

    const ownerAddresses = targets.map(target => target.ownerAddress);

    const listOfMapOfMarketsOfOpenOrders = await Promise.all(ownerAddresses.flatMap(async (ownerAddress) => {
      return (await this.getAllOpenOrders(ownerAddress)); // TODO this method is not the correct one!!!
    }));

    for(const mapOfMarkets of listOfMapOfMarketsOfOpenOrders) {
        for(const mapOfOrders of mapOfMarkets.values()) {
        for (const order of mapOfOrders.values()) {
          temporary.set(order.exchangeId!, order);
        }
      }
    }

    for (const target of targets) {
      orders.concat(
        temporary.filter((openOrder: Order) => {
          return (openOrder.ownerAddress === target.ownerAddress
          && (target.marketName ? openOrder.marketName === target.marketName : true)
          && (
            target.ids?.includes(openOrder.id!)
            || target.exchangeIds?.includes(openOrder.exchangeId!)
          ));
        })
      );
    }

    return orders;
  }

  async getOpenOrders(
    targets: GetOpenOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    const orders = IMap<string, Order>().asMutable();
    const temporary = IMap<string, Order>().asMutable();

    const ownerAddresses = targets.map(target => target.ownerAddress);

    const listOfMapOfMarketsOfOpenOrders = await Promise.all(ownerAddresses.flatMap(async (ownerAddress) => {
      return (await this.getAllOpenOrders(ownerAddress));
    }));

    for(const mapOfMarkets of listOfMapOfMarketsOfOpenOrders) {
        for(const mapOfOrders of mapOfMarkets.values()) {
        for (const order of mapOfOrders.values()) {
          temporary.set(order.exchangeId!, order);
        }
      }
    }

    for (const target of targets) {
      orders.concat(
        temporary.filter((openOrder: Order) => {
          return (openOrder.ownerAddress === target.ownerAddress
          && (target.marketName ? openOrder.marketName === target.marketName : true)
          && (
            target.ids?.includes(openOrder.id!)
            || target.exchangeIds?.includes(openOrder.exchangeId!)
          ));
        })
      );
    }

    return orders;
  }

  async getAllOpenOrdersForMarket(
    marketName: string,
    address: string
  ): Promise<IMap<string, Order>> {
    const market = await this.getMarket(marketName);

    const owner = await this.solana.getAccount(address);

    const serumOpenOrders = await market.market.loadOrdersForOwner(
      this.connection,
      owner.publicKey
    );

    return this.parseToMapOfOrders(market, serumOpenOrders, address);
  }

  async getAllOpenOrdersForMarkets(
    marketNames: string[],
    address: string
  ): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    for (const marketName of marketNames) {
      result.set(
        marketName,
        await this.getAllOpenOrdersForMarket(marketName, address)
      );
    }

    return result;
  }

  async getAllOpenOrders(
    address: string
  ): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getAllOpenOrdersForMarkets(marketNames, address);
  }

  async createOrder(candidate: CreateOrdersRequest): Promise<Order> {
    // TODO Add validation!!!
    const market = await this.getMarket(candidate.marketName);

    const owner = await this.solana.getAccount(candidate.ownerAddress);
    const payer = owner.publicKey;

    // TODO: remove if is incorrect!!!
    // let mintAddress: PublicKey;
    // if (candidate.side.toLowerCase() == OrderSide.BUY.toLowerCase()) {
    //   // mintAddress = market.market.quoteMintAddress;
    //   mintAddress = market.market.baseMintAddress;
    // } else {
    //   // mintAddress = market.market.baseMintAddress;
    //   mintAddress = market.market.quoteMintAddress;
    // }
    //
    // // TODO check if it's correct!!!
    // let payer = await this.solana.findAssociatedTokenAddress(
    //   owner.publicKey,
    //   mintAddress
    // );

    const serumOrderParams: SerumOrderParams<Account> = {
      side: convertOrderSideToSerumSide(candidate.side),
      price: candidate.price,
      size: candidate.amount,
      orderType: convertOrderTypeToSerumType(candidate.type),
      clientId: candidate.id ? new BN(candidate.id) : undefined,
      owner: owner,
      payer: payer
    };

    const signature = await market.market.placeOrder(
      this.connection,
      serumOrderParams
    );

    return convertSerumOrderToOrder(
      market,
      undefined,
      candidate,
      serumOrderParams,
      candidate.ownerAddress,
      OrderStatus.PENDING,
      signature
    );
  }

  async createOrders(
    candidates: CreateOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    // TODO improve to use transactions in the future!!!

    const createdOrders = IMap<string, Order>().asMutable();
    for (const candidateOrder of candidates) {
      const createdOrder = await this.createOrder(candidateOrder);

      // TODO use signature here? the client id is not always available, the exchange id is not available in the response!!!
      createdOrders.set(createdOrder.signature!, createdOrder);
    }

    return createdOrders;
  }

  async cancelOrder(target: CancelOrderRequest): Promise<Order> {
    // TODO Add validation!!!
    const market = await this.getMarket(target.marketName);

    const owner = await this.solana.getAccount(target.ownerAddress);

    const order = await this.getOrder({ ...target });

    order.signature = await market.market.cancelOrder(this.connection, owner, order.order!);

    // TODO what about the status of the order?!!!
    // TODO Important! Probably we need to call the settle funds api function!!!

    return order;
  }

  async cancelOrders(
    targets: CancelOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    // TODO improve to use transactions in the future

    const canceledOrders = IMap<string, Order>().asMutable();

    for (const target of targets) {
      // TODO Add validation!!!
      const market = await this.getMarket(target.marketName);

      const owner = await this.solana.getAccount(target.ownerAddress);

      const orders = await this.getOrders([target]);

      for (const order of orders.values()) {
        order.signature = await market.market.cancelOrder(this.connection, owner, order.order!);

        // TODO what about the status of the order?!!!
        // TODO Important! Probably we need to call the settle funds api function!!!

        canceledOrders.set(order.exchangeId!, order);
      }
    }

    return canceledOrders;
  }

  async cancelAllOpenOrders(address: string): Promise<IMap<string, Order>> {
    const mapOfMapOfOrders = await this.getAllOpenOrders(address);

    const canceledOrders = IMap<string, Order>().asMutable();

    for (const mapOfOrders of mapOfMapOfOrders.values()) {
      for (const order of mapOfOrders.values()) {
        const canceledOrder = await this.cancelOrder({
          marketName: order.marketName,
          ownerAddress: order.ownerAddress!,
          id: order.id,
          exchangeId: order.exchangeId,
        });

        canceledOrders.set(canceledOrder.exchangeId!, canceledOrder);
      }
    }

    return canceledOrders;
  }

  async getFilledOrders(
    targets: GetFilledOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    let result = IMap<string, Order>().asMutable();

    for (const target of targets) {
      let marketsMap = IMap<string, Market>().asMutable();

      if (!target.marketName) {
        marketsMap = await this.getAllMarkets();
      } else {
        marketsMap.set(
          target.marketName,
          await this.getMarket(target.marketName)
        );
      }

      for (const market of marketsMap.values()) {
        // TODO will not work properly because we are loading the fills for everyone and not just for the owner orders!!!
        // TODO check if -1 would also work and which limit is the correct one here!!!
        const orders = await market.market.loadFills(this.connection, 0);

        result = IMap([...result, ...this.parseToMapOfOrders(market, orders, target.ownerAddress!)]).asMutable();
        result = result.filter((order) => {
          order.ownerAddress === target.ownerAddress
          && order.marketName === target.marketName
          && (
            target.ids?.includes(order.id!)
            || target.exchangeIds?.includes(order.exchangeId!)
          )
        });
      }
    }

    return result;
  }

  async getAllFilledOrders(): Promise<IMap<string, Order>> {
    return await this.getFilledOrders([]);
  }
}
