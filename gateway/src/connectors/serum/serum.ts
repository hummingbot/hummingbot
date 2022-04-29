import {Market as SerumMarket, MARKETS,} from '@project-serum/serum';
import {OrderParams as SerumOrderParams,} from '@project-serum/serum/lib/market';
import {Account, Connection, PublicKey} from '@solana/web3.js';
import axios from 'axios';
import BN from "bn.js";
import {Cache, CacheContainer} from 'node-ts-cache';
import {MemoryStorage} from 'node-ts-cache-storage-memory';
import {Solana} from '../../chains/solana/solana';
import {getSerumConfig, SerumConfig} from './serum.config';
import {
  convertArrayOfSerumOrdersToMapOfOrders,
  convertFilledOrderToTicker,
  convertMarketBidsAndAsksToOrderBook,
  convertOrderSideToSerumSide,
  convertOrderTypeToSerumType,
  convertSerumMarketToMarket,
  convertSerumOrderToOrder
} from "./serum.convertors";
import {promiseAllInBatches} from "./serum.helpers";
import {
  BasicSerumMarket,
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
  Ticker,
  TickerNotFoundError,
} from './serum.types';

const caches = {
  instances: new CacheContainer(new MemoryStorage()),
  markets: new CacheContainer(new MemoryStorage()),
};

// const ordersMap = IMap<string, Order>().asMutable();

export type Serumish = Serum;

// TODO Start using the https://www.npmjs.com/package/decimal library!!!
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
   * @param network
   * @private
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
  async getMarket(name?: string): Promise<Market> {
    if (!name) throw new MarketNotFoundError(`No market informed.`);

    const markets = await this.getAllMarkets();

    const market = markets.get(name);

    if (!market) throw new MarketNotFoundError(`Market "${name}" not found.`);

    return market;
  }

  /**
   *
   * @param names
   */
  async getMarkets(names: string[]): Promise<IMap<string, Market>> {
    const markets = IMap<string, Market>().asMutable();

    const getMarket = async(name: string): Promise<void> => {
      const market = await this.getMarket(name);

      markets.set(name, market);
    }

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getMarket, names, 100, 10000);

    return markets;
  }

  /**
   *
   */
  @Cache(caches.markets, { ttl: 60 * 60 })
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

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    // It takes on average about 44s to load all the markets
    await promiseAllInBatches(loadMarket, marketsInformation, 100, 10000);

    return allMarkets;
  }

  async getOrderBook(marketName: string): Promise<OrderBook> {
    const market = await this.getMarket(marketName);

    const asks = await market.market.loadAsks(this.connection);
    const bids = await market.market.loadBids(this.connection);

    return convertMarketBidsAndAsksToOrderBook(
      market,
      asks,
      bids
    );
  }

  async getOrderBooks(marketNames: string[]): Promise<IMap<string, OrderBook>> {
    const orderBooks = IMap<string, OrderBook>().asMutable();

    const getOrderBook = async(marketName: string): Promise<void> => {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getOrderBook, marketNames, 100, 10000);

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

    const getTicker = async(marketName: string): Promise<void> => {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    }

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getTicker, marketNames, 100, 10000);

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

    if (target.marketName) {
      const openOrder = ((await this.getOpenOrdersForMarket(target.marketName, target.ownerAddress)).find(order =>
        order.id === target.id || order.exchangeId === target.exchangeId
      ));

      if (!openOrder)
        throw new OrderNotFoundError(`No open order found with id / exchange id "${target.id} / ${target.exchangeId}".`);

      return openOrder;
    }

    const mapOfOpenOrdersForMarkets = await this.getAllOpenOrders(target.ownerAddress);

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

    throw new OrderNotFoundError(`No open order found with id / exchange id "${target.id} / ${target.exchangeId}".`);
  }

  // TODO check if the implementation returns the correct results!!!
  async getOpenOrders(
    targets: GetOpenOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    const orders = IMap<string, Order>().asMutable();
    let temporary = IMap<string, Order>().asMutable();

    const getOrders = async (target: GetOrdersRequest) => {
      if (target.marketName) {
        temporary.concat(await this.getOpenOrdersForMarket(target.marketName, target.ownerAddress));
      } else {
        (await this.getAllOpenOrders(target.ownerAddress)).reduce((acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
          return acc.concat(mapOfOrders);
        }, temporary);
      }
    };

    await promiseAllInBatches(getOrders, targets, 100, 10000);

    for (const target of targets) {
      orders.concat(
        temporary.filter((order: Order) => {
          return (order.ownerAddress === target.ownerAddress
          && (target.marketName ? order.marketName === target.marketName : true)
          && (
            target.ids?.includes(order.id!)
            || target.exchangeIds?.includes(order.exchangeId!)
          ));
        })
      );
    }

    return orders;
  }

  async getOpenOrdersForMarket(
    marketName: string,
    ownerAddress: string
  ): Promise<IMap<string, Order>> {
    const market = await this.getMarket(marketName);

    const owner = await this.solana.getAccount(ownerAddress);

    const serumOpenOrders = await market.market.loadOrdersForOwner(
      this.connection,
      owner.publicKey
    );

    return convertArrayOfSerumOrdersToMapOfOrders(market, serumOpenOrders, ownerAddress);
  }

  async getOpenOrdersForMarkets(
    marketNames: string[],
    ownerAddress: string
  ): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    const markets = await this.getMarkets(marketNames);

    const getOpenOrders = async (market: Market): Promise<void> => {
      result.set(market.name, await this.getOpenOrdersForMarket(market.name, ownerAddress));
    }

    await promiseAllInBatches<Market, Promise<void>>(
      getOpenOrders, Array.from(markets.values()), 100, 10000
    );

    return result;
  }

  async getAllOpenOrders(
    ownerAddress: string
  ): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getOpenOrdersForMarkets(marketNames, ownerAddress);
  }

  async getFilledOrder(target: GetFilledOrderRequest): Promise<Order> {
    if (!target.id && !target.exchangeId)
      throw new OrderNotFoundError('No client id or exchange id provided.');

    if (!target.ownerAddress)
      throw new OrderNotFoundError(`No owner address provided for order "${target.id} / ${target.exchangeId}".`);

    if (target.marketName) {
      const filledOrder = ((await this.getFilledOrdersForMarket(target.marketName)).find(order =>
        order.id === target.id || order.exchangeId === target.exchangeId
      ));

      if (!filledOrder)
        throw new OrderNotFoundError(`No open order found with id / exchange id "${target.id} / ${target.exchangeId}".`);

      return filledOrder;
    }

    const mapOfFilledOrdersForMarkets = await this.getAllFilledOrders();

    for (const mapOfFilledOrdersForMarket of mapOfFilledOrdersForMarkets.values()) {
      for (const filledOrder of mapOfFilledOrdersForMarket.values()) {
        if (
          filledOrder.id === target.id ||
          filledOrder.exchangeId === target.exchangeId
        ) {
          return filledOrder;
        }
      }
    }

    throw new OrderNotFoundError(`No filled order found with id / exchange id "${target.id} / ${target.exchangeId}".`);
  }

  // TODO check if the implementation returns the correct results!!!
  async getFilledOrders(
    targets: GetFilledOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    const orders = IMap<string, Order>().asMutable();
    let temporary = IMap<string, Order>().asMutable();

    const getOrders = async (target: GetOrdersRequest) => {
      if (target.marketName) {
        temporary.concat(await this.getFilledOrdersForMarket(target.marketName));
      } else {
        (await this.getAllFilledOrders()).reduce((acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
          return acc.concat(mapOfOrders);
        }, temporary);
      }
    };

    await promiseAllInBatches(getOrders, targets, 100, 10000);

    for (const target of targets) {
      orders.concat(
        temporary.filter((order: Order) => {
          return (order.ownerAddress === target.ownerAddress
          && (target.marketName ? order.marketName === target.marketName : true)
          && (
            target.ids?.includes(order.id!)
            || target.exchangeIds?.includes(order.exchangeId!)
          ));
        })
      );
    }

    return orders;
  }

  async getFilledOrdersForMarket(marketName: string): Promise<IMap<string, Order>> {
    const market = await this.getMarket(marketName);

    const orders = await market.market.loadFills(this.connection, 0);

    return convertArrayOfSerumOrdersToMapOfOrders(market, orders);
  }

  async getFilledOrdersForMarkets(marketNames: string[]): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    const markets = await this.getMarkets(marketNames);

    const getFilledOrders = async (market: Market): Promise<void> => {
      result.set(market.name, await this.getFilledOrdersForMarket(market.name));
    }

    await promiseAllInBatches<Market, Promise<void>>(
      getFilledOrders, Array.from(markets.values()), 100, 10000
    );

    return result;
  }

  async getAllFilledOrders(): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getFilledOrdersForMarkets(marketNames);
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

  // TODO check if the implementation returns the correct results!!!
  async getOrders(targets: GetOrdersRequest[]): Promise<IMap<string, Order>> {
    const orders = IMap<string, Order>().asMutable();
    let temporary = IMap<string, Order>().asMutable();

    const getOrders = async (target: GetOrdersRequest) => {
      if (target.marketName) {
        const openOrders = await this.getOpenOrdersForMarket(target.marketName, target.ownerAddress);
        const filledOrders = await this.getFilledOrdersForMarket(target.marketName);
        temporary.concat(openOrders).concat(filledOrders);
      } else {
        (await this.getAllOpenOrders(target.ownerAddress)).reduce((acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
          return acc.concat(mapOfOrders);
        }, temporary);

        (await this.getAllFilledOrders()).reduce((acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
          return acc.concat(mapOfOrders);
        }, temporary);
      }
    };

    await promiseAllInBatches(getOrders, targets, 100, 10000);

    for (const target of targets) {
      orders.concat(
        temporary.filter((order: Order) => {
          return (order.ownerAddress === target.ownerAddress
          && (target.marketName ? order.marketName === target.marketName : true)
          && (
            target.ids?.includes(order.id!)
            || target.exchangeIds?.includes(order.exchangeId!)
          ));
        })
      );
    }

    return orders;
  }

  // TODO check if the implementation returns the correct results!!!
  async getOrdersForMarket(marketName: string, ownerAddress: string): Promise<IMap<string, Order>> {
    const orders = (await this.getOpenOrdersForMarket(marketName, ownerAddress));
    orders.concat(await this.getFilledOrdersForMarket(marketName));

    return orders;
  }

  // TODO check if the implementation returns the correct results!!!
  async getOrdersForMarkets(marketNames: string[], ownerAddress: string): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    const markets = await this.getMarkets(marketNames);

    const getOrders = async (market: Market): Promise<void> => {
      result.set(market.name, await this.getOrdersForMarket(market.name, ownerAddress));
    }

    await promiseAllInBatches<Market, Promise<void>>(
      getOrders, Array.from(markets.values()), 100, 10000
    );

    return result;
  }

  // TODO check if the implementation returns the correct results!!!
  async getAllOrders(ownerAddress: string): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getOrdersForMarkets(marketNames, ownerAddress);
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

  async cancelAllOpenOrders(ownerAddress: string): Promise<IMap<string, Order>> {
    const mapOfMapOfOrders = await this.getAllOpenOrders(ownerAddress);

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
}
