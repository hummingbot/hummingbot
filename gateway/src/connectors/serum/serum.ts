import {MARKETS} from '@project-serum/serum';
import {OpenOrders} from "@project-serum/serum/lib/market";
import {Account, AccountInfo, Connection, PublicKey} from '@solana/web3.js';
import axios from 'axios';
import BN from "bn.js";
import {Cache, CacheContainer} from 'node-ts-cache';
import {MemoryStorage} from 'node-ts-cache-storage-memory';
import {Solana} from '../../chains/solana/solana';
import {logger} from './../../services/logger';
import {getSerumConfig, SerumConfig} from './serum.config';
import {promisesBatchSize, promisesDelayInMilliseconds, serumMarketsTTL} from "./serum.constants";
import {
  convertArrayOfSerumOrdersToMapOfOrders,
  convertMarketBidsAndAsksToOrderBook,
  convertOrderSideToSerumSide,
  convertOrderTypeToSerumType,
  convertSerumMarketToMarket,
  convertSerumOrderToOrder,
  convertToTicker
} from "./serum.convertors";
import {getRandonBN, promiseAllInBatches} from "./serum.helpers";
import {
  BasicSerumMarket,
  CancelOrderRequest,
  CancelOrdersRequest,
  CreateOrdersRequest,
  Fund, FundsSettlementError,
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
  SerumMarket,
  SerumMarketOptions,
  SerumOpenOrders,
  SerumOrder,
  SerumOrderBook,
  SerumOrderParams,
  Ticker,
  TickerNotFoundError,
  TickerSource,
} from './serum.types';
import {validateCreateOrderRequest} from "./serum.validators";

const caches = {
  instances: new CacheContainer(new MemoryStorage()),
  markets: new CacheContainer(new MemoryStorage()),
  serumFindQuoteTokenAccountsForOwner: new CacheContainer(new MemoryStorage()),
  serumFindBaseTokenAccountsForOwner: new CacheContainer(new MemoryStorage()),
};

export type Serumish = Serum;

/**
 * Serum is a wrapper around the Serum API.
 *
 * // TODO Listen the events from the serum api to automatically settle the funds (specially when filling orders)!!!
 */
export class Serum {
  private initializing: boolean = false;

  private readonly config: SerumConfig.Config;
  private readonly connection: Connection;
  private solana!: Solana;
  private _ready: boolean = false;

  chain: string;
  network: string;
  readonly connector: string = 'serum';

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

    this.config = getSerumConfig(network)

    this.connection = new Connection(this.config.network.rpcURL);
  }

  /**
   * 1 external API call.
   *
   * @param connection
   * @param address
   * @param options
   * @param programId
   * @param layoutOverride
   * @private
   */
  private async serumLoadMarket(connection: Connection, address: PublicKey, options: SerumMarketOptions | undefined, programId: PublicKey, layoutOverride?: any): Promise<SerumMarket> {
    const result = await SerumMarket.load(connection,address, options, programId, layoutOverride);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @private
   */
  private async serumMarketLoadBids(market: SerumMarket, connection: Connection): Promise<SerumOrderBook> {
    const result =  await market.loadBids(connection);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @private
   */
  private async serumMarketLoadAsks(market: SerumMarket, connection: Connection): Promise<SerumOrderBook> {
    const result =  await market.loadAsks(connection);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param limit
   * @private
   */
  private async serumMarketLoadFills(market: SerumMarket, connection: Connection, limit?: number): Promise<any[]> {
    const result = await market.loadFills(connection, limit);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param ownerAddress
   * @param cacheDurationMs
   * @private
   */
  private async serumMarketLoadOrdersForOwner(market: SerumMarket, connection: Connection, ownerAddress: PublicKey, cacheDurationMs?: number): Promise<SerumOrder[]> {
    const result =  await market.loadOrdersForOwner(connection, ownerAddress, cacheDurationMs);
    
    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param owner
   * @param payer
   * @param side
   * @param price
   * @param size
   * @param orderType
   * @param clientId
   * @param openOrdersAddressKey
   * @param openOrdersAccount
   * @param feeDiscountPubkey
   * @param maxTs
   * @param replaceIfExists
   * @private
   */
  private async serumMarketPlaceOrder(market: SerumMarket, connection: Connection, { owner, payer, side, price, size, orderType, clientId, openOrdersAddressKey, openOrdersAccount, feeDiscountPubkey, maxTs, replaceIfExists, }: SerumOrderParams<Account>): Promise<string> {
    const result =  await market.placeOrder(
      connection,
      { owner, payer, side, price, size, orderType, clientId, openOrdersAddressKey, openOrdersAccount, feeDiscountPubkey, maxTs, replaceIfExists, }
    );

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param owner
   * @param order
   * @private
   */
  private async serumMarketCancelOrder(market: SerumMarket, connection: Connection, owner: Account, order: SerumOrder): Promise<string> {
    const result = await market.cancelOrder(connection, owner, order);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param ownerAddress
   * @param cacheDurationMs
   * @private
   */
  private async serumFindOpenOrdersAccountsForOwner(market: SerumMarket, connection: Connection, ownerAddress: PublicKey, cacheDurationMs?: number): Promise<SerumOpenOrders[]> {
    const result = await market.findOpenOrdersAccountsForOwner(connection, ownerAddress, cacheDurationMs);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param ownerAddress
   * @param includeUnwrappedSol
   * @private
   */
  @Cache(caches.serumFindBaseTokenAccountsForOwner, { isCachedForever: true })
  private async serumFindBaseTokenAccountsForOwner(market: SerumMarket, connection: Connection, ownerAddress: PublicKey, includeUnwrappedSol?: boolean): Promise<Array<{pubkey: PublicKey; account: AccountInfo<Buffer>;}>> {
    const result = await market.findBaseTokenAccountsForOwner(connection, ownerAddress, includeUnwrappedSol);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param ownerAddress
   * @param includeUnwrappedSol
   * @private
   */
  @Cache(caches.serumFindQuoteTokenAccountsForOwner, { isCachedForever: true })
  private async serumFindQuoteTokenAccountsForOwner(market: SerumMarket, connection: Connection, ownerAddress: PublicKey, includeUnwrappedSol?: boolean): Promise<Array<{pubkey: PublicKey; account: AccountInfo<Buffer>;}>> {
    const result = await market.findQuoteTokenAccountsForOwner(connection, ownerAddress, includeUnwrappedSol);

    return result;
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param owner
   * @param openOrders
   * @param baseWallet
   * @param quoteWallet
   * @param referrerQuoteWallet
   * @private
   */
  private async serumSettleFunds(market: SerumMarket, connection: Connection, owner: Account, openOrders: OpenOrders, baseWallet: PublicKey, quoteWallet: PublicKey, referrerQuoteWallet?: PublicKey | null): Promise<string> {
    const result = await market.settleFunds(connection, owner, openOrders, baseWallet, quoteWallet, referrerQuoteWallet);

    return result;
  }

  /**
   * Get the Serum instance for the given chain and network.
   * Is cached forever.
   *
   * $numberOfAllowedMarkets external API calls.
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
   *
   * $numberOfAllowedMarkets external API calls.
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

  /**
   * 0 external API call.
   */
  ready(): boolean {
    return this._ready;
  }

  /**
   * 0 external API call.
   */
  getConnection(): Connection {
    return this.connection;
  }

  /**
   * 0 external API call.
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
   * 0 external API calls.
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
    await promiseAllInBatches(getMarket, names, promisesBatchSize, promisesDelayInMilliseconds);

    return markets;
  }

  /**
   * $numberOfAllowedMarkets external API calls.
   */
  @Cache(caches.markets, { ttl: serumMarketsTTL })
  async getAllMarkets(): Promise<IMap<string, Market>> {
    const allMarkets = IMap<string, Market>().asMutable();

    const marketsURL =
      this.config.markets.url
      || 'https://raw.githubusercontent.com/project-serum/serum-ts/master/packages/serum/src/markets.json';

    let marketsInformation: BasicSerumMarket[];

    try {
      marketsInformation = (await axios.get(marketsURL)).data;
    } catch (e) {
      marketsInformation = MARKETS;
    }

    marketsInformation = marketsInformation.filter(
      item =>
        !item.deprecated
        && (this.config.markets.blacklist.length ? !this.config.markets.blacklist.includes(item.name) : true)
        && (this.config.markets.whiteList.length ? this.config.markets.whiteList.includes(item.name) : true)
    );

    const loadMarket = async(market: BasicSerumMarket): Promise<void> => {
      const serumMarket = await this.serumLoadMarket(
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
    await promiseAllInBatches(loadMarket, marketsInformation, promisesBatchSize, promisesDelayInMilliseconds);

    return allMarkets;
  }

  /**
   * 2 external API calls.
   *
   * @param marketName
   */
  async getOrderBook(marketName: string): Promise<OrderBook> {
    const market = await this.getMarket(marketName);

    const asks = await this.serumMarketLoadAsks(market.market, this.connection);
    const bids = await this.serumMarketLoadBids(market.market, this.connection);

    return convertMarketBidsAndAsksToOrderBook(
      market,
      asks,
      bids
    );
  }

  /**
   * 2*$numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   */
  async getOrderBooks(marketNames: string[]): Promise<IMap<string, OrderBook>> {
    const orderBooks = IMap<string, OrderBook>().asMutable();

    const getOrderBook = async(marketName: string): Promise<void> => {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getOrderBook, marketNames, promisesBatchSize, promisesDelayInMilliseconds);

    return orderBooks;
  }

  /**
   * 2*$numberOfAllowedMarkets external API calls.
   */
  async getAllOrderBooks(): Promise<IMap<string, OrderBook>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.getOrderBooks(marketNames);
  }

  /**
   * 1 external API call.
   *
   * @param marketName
   */
  async getTicker(marketName: string): Promise<Ticker> {
    const market = await this.getMarket(marketName);

    try {
      if (this.config.tickers.source === TickerSource.NOMIMCS) {
        const result: { price: any, last_updated_at: any } = (await axios.get(
          this.config.tickers.url
          || `https://nomics.com/data/exchange-markets-ticker?convert=USD&exchange=serum_dex&interval=1d&market=${market.address}`
        )).data.items[0];

        return convertToTicker(result);
      }

      throw new TickerNotFoundError(`Ticker source (${this.config.tickers.source}) not supported, check your serum configuration file.`);
    } catch (exception) {
      throw new TickerNotFoundError(`Ticker data is currently not available for market "${marketName}".`);
    }

    // // The implementation below should be the preferred one, but it is not always available
    // const market = await this.getMarket(marketName);
    //
    // const filledOrders = await this.serumMarketLoadFills(market.market, this.connection);
    // if (!filledOrders || !filledOrders.length)
    //   throw new TickerNotFoundError(`Ticker data is currently not available for market "${marketName}".`);
    //
    // const mostRecentFilledOrder = filledOrders[0];
    //
    // return convertToTicker(Date.now(), mostRecentFilledOrder);
  }

  /**
   * $numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   */
  async getTickers(marketNames: string[]): Promise<IMap<string, Ticker>> {
    const tickers = IMap<string, Ticker>().asMutable();

    const getTicker = async(marketName: string): Promise<void> => {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    }

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getTicker, marketNames, promisesBatchSize, promisesDelayInMilliseconds);

    return tickers;
  }

  /**
   * $numberOfAllowedMarkets external API calls.
   */
  async getAllTickers(): Promise<IMap<string, Ticker>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getTickers(marketNames);
  }

  /**
   * 1 or $numberOfAllowedMarkets external API calls.
   * 
   * @param target
   */
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

      openOrder.status = OrderStatus.OPEN;

      return openOrder;
    }

    const mapOfOpenOrdersForMarkets = await this.getAllOpenOrders(target.ownerAddress);

    for (const mapOfOpenOrdersForMarket of mapOfOpenOrdersForMarkets.values()) {
      for (const openOrder of mapOfOpenOrdersForMarket.values()) {
        if (
          openOrder.id === target.id ||
          openOrder.exchangeId === target.exchangeId
        ) {
          openOrder.status = OrderStatus.OPEN;

          return openOrder;
        }
      }
    }

    throw new OrderNotFoundError(`No open order found with id / exchange id "${target.id} / ${target.exchangeId}".`);
  }

  /**
   * $numberOfTargets or $numberOfTargets*$numberOfAllowedMarkets external API calls.
   *
   * @param targets
   */
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

    await promiseAllInBatches(getOrders, targets, promisesBatchSize, promisesDelayInMilliseconds);

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

  /**
   * 1 external API call.
   *
   * @param marketName
   * @param ownerAddress
   */
  async getOpenOrdersForMarket(
    marketName: string,
    ownerAddress: string
  ): Promise<IMap<string, Order>> {
    const market = await this.getMarket(marketName);

    const owner = await this.solana.getAccount(ownerAddress);

    const serumOpenOrders = await this.serumMarketLoadOrdersForOwner(market.market, this.connection, owner.publicKey);

    return convertArrayOfSerumOrdersToMapOfOrders(market, serumOpenOrders, ownerAddress, OrderStatus.OPEN);
  }

  /**
   * $numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   * @param ownerAddress
   */
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
      getOpenOrders, Array.from(markets.values()), promisesBatchSize, promisesDelayInMilliseconds
    );

    return result;
  }

  /**
   * $numberOfAllowedMarkets external API calls.
   *
   * @param ownerAddress
   */
  async getAllOpenOrders(
    ownerAddress: string
  ): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getOpenOrdersForMarkets(marketNames, ownerAddress);
  }

  /**
   * 1 or $numberOfAllowedMarkets external API calls.
   *
   * @param target
   */
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

      filledOrder.status = OrderStatus.FILLED;

      return filledOrder;
    }

    const mapOfFilledOrdersForMarkets = await this.getAllFilledOrders();

    for (const mapOfFilledOrdersForMarket of mapOfFilledOrdersForMarkets.values()) {
      for (const filledOrder of mapOfFilledOrdersForMarket.values()) {
        if (
          filledOrder.id === target.id ||
          filledOrder.exchangeId === target.exchangeId
        ) {
          filledOrder.status = OrderStatus.FILLED;

          return filledOrder;
        }
      }
    }

    throw new OrderNotFoundError(`No filled order found with id / exchange id "${target.id} / ${target.exchangeId}".`);
  }

  /**
   * $numberOfTargets or $numberOfTargets*$numberOfAllowedMarkets external API calls.
   *
   * @param targets
   */
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

    await promiseAllInBatches(getOrders, targets, promisesBatchSize, promisesDelayInMilliseconds);

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

  /**
   * 1 external API calls.
   *
   * @param marketName
   */
  async getFilledOrdersForMarket(marketName: string): Promise<IMap<string, Order>> {
    const market = await this.getMarket(marketName);

    const orders = await this.serumMarketLoadFills(market.market, this.connection, 0);

    // TODO check if it's possible to get the owner address
    return convertArrayOfSerumOrdersToMapOfOrders(market, orders, undefined, OrderStatus.FILLED);
  }

  /**
   * $numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   */
  async getFilledOrdersForMarkets(marketNames: string[]): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    const markets = await this.getMarkets(marketNames);

    const getFilledOrders = async (market: Market): Promise<void> => {
      result.set(market.name, await this.getFilledOrdersForMarket(market.name));
    }

    await promiseAllInBatches<Market, Promise<void>>(
      getFilledOrders, Array.from(markets.values()), promisesBatchSize, promisesDelayInMilliseconds
    );

    return result;
  }

  /**
   * $numberOfAllowedMarkets external API calls.
   */
  async getAllFilledOrders(): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getFilledOrdersForMarkets(marketNames);
  }

  /**
   * (1 or 2) or ($numberOfAllowedMarkets or 2*$numberOfAllowedMarkets) external API calls.
   *
   * @param target
   */
  async getOrder(target: GetOrderRequest): Promise<Order> {
    if (!target.id && !target.exchangeId)
      throw new OrderNotFoundError('No client id or exchange id provided.');

    try {
      return await this.getOpenOrder(target);
    } catch (exception) {
      if (exception instanceof OrderNotFoundError) {
        try {
          return await this.getFilledOrder(target);
        } catch (exception2) {
          if (exception2 instanceof OrderNotFoundError) {
            throw new OrderNotFoundError(`No order found with id / exchange id "${target.id} / ${target.exchangeId}".`);
          }
        }
      }

      throw exception;
    }
  }

  /**
   * 2*$numberOfTargets or 2*$numberOfTargets*$numberOfAllowedMarkets external API calls.
   *
   * @param targets
   */
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

    await promiseAllInBatches(getOrders, targets, promisesBatchSize, promisesDelayInMilliseconds);

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

  /**
   * 2 external API calls.
   *
   * @param marketName
   * @param ownerAddress
   */
  async getOrdersForMarket(marketName: string, ownerAddress: string): Promise<IMap<string, Order>> {
    const orders = (await this.getOpenOrdersForMarket(marketName, ownerAddress));
    orders.concat(await this.getFilledOrdersForMarket(marketName));

    return orders;
  }

  /**
   * 2*$numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   * @param ownerAddress
   */
  async getOrdersForMarkets(marketNames: string[], ownerAddress: string): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    const markets = await this.getMarkets(marketNames);

    const getOrders = async (market: Market): Promise<void> => {
      result.set(market.name, await this.getOrdersForMarket(market.name, ownerAddress));
    }

    await promiseAllInBatches<Market, Promise<void>>(
      getOrders, Array.from(markets.values()), promisesBatchSize, promisesDelayInMilliseconds
    );

    return result;
  }

  /**
   * 2*$numberOfAllMarkets external API calls.
   *
   * @param ownerAddress
   */
  async getAllOrders(ownerAddress: string): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getOrdersForMarkets(marketNames, ownerAddress);
  }

  /**
   * 1 external API call.
   *
   * @param candidate
   */
  async createOrder(candidate: CreateOrdersRequest): Promise<Order> {
    const market = await this.getMarket(candidate.marketName);

    const owner = await this.solana.getAccount(candidate.ownerAddress);
    const payer = owner.publicKey;

    const serumOrderParams: SerumOrderParams<Account> = {
      side: convertOrderSideToSerumSide(candidate.side),
      price: candidate.price,
      size: candidate.amount,
      orderType: convertOrderTypeToSerumType(candidate.type),
      clientId: candidate.id ? new BN(candidate.id) : getRandonBN(),
      owner: owner,
      payer: payer
    };

    try {
      const signature = await this.serumMarketPlaceOrder(market.market, this.connection, serumOrderParams);

      return convertSerumOrderToOrder(
        market,
        undefined,
        candidate,
        serumOrderParams,
        candidate.ownerAddress,
        OrderStatus.OPEN,
        signature
      );
    } catch (exception: any) {
      if (exception.message.includes('It is unknown if it succeeded or failed.')) {
        return convertSerumOrderToOrder(
          market,
          undefined,
          candidate,
          serumOrderParams,
          candidate.ownerAddress,
          OrderStatus.CREATION_PENDING,
          undefined
        );
      }

      throw exception;
    }
  }

  /**
   * $numberOfCandidates external API calls.
   *
   * @param candidates
   */
  async createOrders(
    candidates: CreateOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    // TODO Improve to use a single transaction!!!
    // TODO Try to do a trial and error to find the limits!!!

    const createdOrders = IMap<string, Order>().asMutable();
    for (const candidateOrder of candidates) {
      const createdOrder = await this.createOrder(candidateOrder);

      createdOrders.set(createdOrder.id!, createdOrder);
    }

    return createdOrders;
  }

  /**
   * 1 external API call.
   *
   * @param target
   */
  async cancelOrder(target: CancelOrderRequest): Promise<Order> {
    // TODO Add validation!!!
    const market = await this.getMarket(target.marketName);

    const owner = await this.solana.getAccount(target.ownerAddress);

    const order = await this.getOpenOrder({ ...target });

    try {
      order.signature = await this.serumMarketCancelOrder(market.market, this.connection, owner, order.order!);

      order.status = OrderStatus.CANCELED;

      return order;
    } catch (exception: any) {
      if (exception.message.includes('It is unknown if it succeeded or failed.')) {
        order.status = OrderStatus.CANCELATION_PENDING;

        return order;
      }

      throw exception;
    }
  }

  /**
   * $numberOfTargets external API calls.
   * TODO Add validation!!!
   *
   * @param targets
   */
  async cancelOrders(
    targets: CancelOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    // TODO improve to use a single transaction!!!

    const canceledOrders = IMap<string, Order>().asMutable();

    for (const target of targets) {
      const market = await this.getMarket(target.marketName);

      const owner = await this.solana.getAccount(target.ownerAddress);

      const orders = await this.getOrders([target]);

      for (const order of orders.values()) {
        order.signature = await market.market.cancelOrder(this.connection, owner, order.order!);
        order.status = OrderStatus.CANCELED;

        canceledOrders.set(order.exchangeId!, order);
      }
    }

    return canceledOrders;
  }

  /**
   * $numberOfOpenOrders external API calls.
   *
   * @param ownerAddress
   */
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

  /**
   * 3*$numberOfOpenOrdersAccountsForMarket external API calls.
   *
   * @param marketName
   * @param ownerAddress
   */
  async settleFundsForMarket(marketName: string, ownerAddress: string): Promise<Fund> {
    let errors = '';
    const market = await this.getMarket(marketName);
    const owner = await this.solana.getAccount(ownerAddress);

    for (const openOrders of await this.serumFindOpenOrdersAccountsForOwner(
      market.market,
      this.connection,
      owner.publicKey,
    )) {
      if (openOrders.baseTokenFree.gt(new BN(0)) || openOrders.quoteTokenFree.gt(new BN(0))) {
        const base = await this.serumFindBaseTokenAccountsForOwner(market.market, this.connection, owner.publicKey, true);
        const baseTokenAccount = base[0].pubkey;

        const quote = await this.serumFindQuoteTokenAccountsForOwner(market.market, this.connection, owner.publicKey, true);
        const quoteTokenAccount = quote[0].pubkey;

        try {
          // TODO improve to use a single transaction!!!
          await this.serumSettleFunds(
            market.market,
            this.connection,
            owner,
            openOrders,
            baseTokenAccount,
            quoteTokenAccount,
          );
        } catch (exception: any) {
          if (exception.message.includes('It is unknown if it succeeded or failed.')) {
            errors += `${exception.message}\n`;

            logger.warn(`${exception.message}`);

            continue;
          }

          throw exception;
        }
      }
    }

    if (errors) throw new FundsSettlementError(`Unknown state when settling the funds for the market "${marketName}":\n${errors}`);
  }

  /**
   * 3*$numberOfOpenOrdersAccountsForMarket*$numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   * @param ownerAddress
   */
  async settleFundsForMarkets(marketNames: string[], ownerAddress: string): Promise<IMap<string, Fund>> {
    const funds = IMap<string, Fund>().asMutable();

    const settleFunds = async(marketName: string): Promise<void> => {
      const fund = await this.settleFundsForMarket(marketName, ownerAddress);

      funds.set(marketName, fund);
    }

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(settleFunds, marketNames, promisesBatchSize, promisesDelayInMilliseconds);

    return funds;
  }

  /**
   * 3*$numberOfOpenOrdersAccountsForMarket*$numberOfAllowedMarkets external API calls.
   *
   * @param ownerAddress
   */
  async settleAllFunds(ownerAddress: string): Promise<IMap<string, Fund>>{
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.settleFundsForMarkets(marketNames, ownerAddress);
  }
}
