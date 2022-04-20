import {Account, Connection, PublicKey} from '@solana/web3.js';
import {Market as SerumMarket, MARKETS, Orderbook as SerumOrderBook,} from '@project-serum/serum';
import {Map as ImmutableMap} from 'immutable';
import {Solana} from '../../chains/solana/solana';
import {getSerumConfig, SerumConfig} from './serum.config';
import {
  CancelOrdersRequest,
  CreateOrdersRequest,
  GetFilledOrderRequest,
  GetFilledOrdersRequest,
  GetOpenOrderRequest,
  GetOrdersRequest,
  Market,
  MarketNotFoundError,
  Order,
  OrderBook,
  OrderNotFoundError,
  OrderSide,
  OrderStatus,
  Ticker,
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

const caches = {
  instances: new CacheContainer(new MemoryStorage()),

  market: new CacheContainer(new MemoryStorage()),
  markets: new CacheContainer(new MemoryStorage()),
  allMarkets: new CacheContainer(new MemoryStorage()),
};

export type Serumish = Serum;

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
      asks: this.parseToMapOfOrders(market, asks),
      bids: this.parseToMapOfOrders(market, bids),
      orderBook: {
        asks: asks,
        bids: bids,
      },
    } as OrderBook;
  }

  private parseToMapOfOrders(
    market: Market,
    orders: SerumOrder[] | SerumOrderBook | any[]
  ): ImmutableMap<string, Order> {
    const result = ImmutableMap<string, Order>().asMutable();

    for (const order of orders) {
      result.set(order.orderId, convertSerumOrderToOrder(market, order));
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

  /**
   *
   * @param name
   */
  @Cache(caches.market, { isCachedForever: true })
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
  @Cache(caches.markets, { ttl: 60 * 60 })
  async getMarkets(names: string[]): Promise<ImmutableMap<string, Market>> {
    const markets = ImmutableMap<string, Market>().asMutable();

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
  async getAllMarkets(): Promise<ImmutableMap<string, Market>> {
    const allMarkets = ImmutableMap<string, Market>().asMutable();

    // TODO use fetch to retrieve the markets instead of using the JSON!!!
    // TODO change the code to use a background task and load in parallel (using batches) the markets!!!
    for (const market of MARKETS.filter(market => ['BTC/USDT', 'ETH/USDT'].includes(market.name))) {
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

  async getOrderBooks(marketNames: string[]): Promise<ImmutableMap<string, OrderBook>> {
    const orderBooks = ImmutableMap<string, OrderBook>().asMutable();

    for (const marketName of marketNames) {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    return orderBooks;
  }

  async getAllOrderBooks(): Promise<ImmutableMap<string, OrderBook>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.getOrderBooks(marketNames);
  }

  async getTicker(marketName: string): Promise<Ticker> {
    const market = await this.getMarket(marketName);

    const lastFilledOrder = (await market.market.loadFills(this.connection, 10));

    console.log(JSON.stringify(lastFilledOrder, null, 2));

    return convertFilledOrderToTicker(lastFilledOrder[0]);
  }

  async getTickers(marketNames: string[]): Promise<ImmutableMap<string, Ticker>> {
    const tickers = ImmutableMap<string, Ticker>().asMutable();

    for (const marketName of marketNames) {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    }

    return tickers;
  }

  async getAllTickers(): Promise<ImmutableMap<string, Ticker>> {
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

  async getOrder(target: GetOrdersRequest): Promise<Order> {
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

  async getOrders(targets: GetOrdersRequest[]): Promise<ImmutableMap<string, Order>> {
    const orders = ImmutableMap<string, Order>().asMutable();

    for (const target of targets) {
      const order = await this.getOrder(target);

      orders.set(order.exchangeId!, order);
    }

    return orders;
  }

  async getOpenOrders(
    targets: GetOpenOrderRequest[]
  ): Promise<ImmutableMap<string, Order>> {
    const orders = ImmutableMap<string, Order>().asMutable();

    for (const target of targets) {
      const order = await this.getOpenOrder(target);

      orders.set(order.exchangeId!, order);
    }

    return orders;
  }

  async getAllOpenOrdersForMarket(
    marketName: string,
    address: string
  ): Promise<ImmutableMap<string, Order>> {
    const market = await this.getMarket(marketName);

    const owner = await this.solana.getAccount(address);

    const serumOpenOrders = await market.market.loadOrdersForOwner(
      this.connection,
      owner.publicKey
    );

    return this.parseToMapOfOrders(market, serumOpenOrders);
  }

  async getAllOpenOrdersForMarkets(
    marketNames: string[],
    address: string
  ): Promise<ImmutableMap<string, ImmutableMap<string, Order>>> {
    const result = ImmutableMap<string, ImmutableMap<string, Order>>().asMutable();

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
  ): Promise<ImmutableMap<string, ImmutableMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getAllOpenOrdersForMarkets(marketNames, address);
  }

  async createOrder(candidate: CreateOrdersRequest): Promise<Order> {
    // TODO Add validation!!!
    const market = await this.getMarket(candidate.marketName);

    const owner = await this.solana.getAccount(candidate.ownerAddress);

    let mintAddress: PublicKey;
    if (candidate.side.toLowerCase() == OrderSide.BUY.toLowerCase()) {
      mintAddress = market.market.quoteMintAddress;
    } else {
      mintAddress = market.market.baseMintAddress;
    }

    const serumOrderParams: SerumOrderParams<Account> = {
      side: convertOrderSideToSerumSide(candidate.side),
      price: candidate.price,
      size: candidate.amount,
      orderType: convertOrderTypeToSerumType(candidate.type),
      clientId: candidate.id ? new BN(candidate.id) : undefined,
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

    return convertSerumOrderToOrder(
      market,
      undefined,
      candidate,
      serumOrderParams,
      OrderStatus.PENDING,
      signature
    );
  }

  async createOrders(
    candidates: CreateOrdersRequest[]
  ): Promise<ImmutableMap<string, Order>> {
    // TODO improve to use transactions in the future

    const createdOrders = ImmutableMap<string, Order>().asMutable();
    for (const candidateOrder of candidates) {
      const createdOrder = await this.createOrder(candidateOrder);

      createdOrders.set(createdOrder.exchangeId!, createdOrder);
    }

    return createdOrders;
  }

  async cancelOrder(target: CancelOrdersRequest): Promise<any> {
    // TODO Add validation!!!
    const market = await this.getMarket(target.marketName);

    const owner = await this.solana.getAccount(target.ownerAddress);

    const order = await this.getOrder({ ...target });

    await market.market.cancelOrder(this.connection, owner, order.order!);
  }

  async cancelOrders(
    targets: CancelOrdersRequest[]
  ): Promise<ImmutableMap<string, Order>> {
    // TODO improve to use transactions in the future

    const canceledOrders = ImmutableMap<string, Order>().asMutable();

    for (const target of targets) {
      const canceledOrder = await this.cancelOrder({
        marketName: target.marketName,
        ownerAddress: target.ownerAddress,
        id: target.id,
        exchangeId: target.exchangeId,
      });

      canceledOrders.set(canceledOrder.id, canceledOrder);
    }

    return canceledOrders;
  }

  async cancelAllOpenOrders(address: string): Promise<ImmutableMap<string, Order>> {
    const mapOfMapOfOrders = await this.getAllOpenOrders(address);

    const canceledOrders = ImmutableMap<string, Order>().asMutable();

    for (const mapOfOrders of mapOfMapOfOrders.values()) {
      for (const order of mapOfOrders.values()) {
        await this.cancelOrder({
          marketName: order.marketName,
          ownerAddress: order.ownerAddress,
          id: order.id,
          exchangeId: order.exchangeId,
        });

        canceledOrders.set(order.exchangeId!, order);
      }
    }

    return canceledOrders;
  }

  async getFilledOrders(
    targets: GetFilledOrdersRequest[]
  ): Promise<ImmutableMap<string, Order>> {
    let result = ImmutableMap<string, Order>().asMutable();

    for (const target of targets) {
      let marketsMap = ImmutableMap<string, Market>().asMutable();

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
        // TODO check if -1 would also work!!!
        const orders = await market.market.loadFills(this.connection, 0);

        result = ImmutableMap([...result, ...this.parseToMapOfOrders(market, orders)]).asMutable();
      }
    }

    return result;
  }

  async getAllFilledOrders(): Promise<ImmutableMap<string, Order>> {
    return await this.getFilledOrders([]);
  }
}
