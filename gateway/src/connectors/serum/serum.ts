import { MARKETS } from '@project-serum/serum';
import { TokenInfo } from '@solana/spl-token-registry';
import { Account as TokenAccount } from '@solana/spl-token/lib/types/state/account';
import {
  Account,
  AccountInfo,
  Connection,
  PublicKey,
  Transaction,
  TransactionSignature,
} from '@solana/web3.js';
import axios from 'axios';
import BN from 'bn.js';
import { Cache, CacheContainer } from 'node-ts-cache';
import { MemoryStorage } from 'node-ts-cache-storage-memory';
import { Solana } from '../../chains/solana/solana';
import {
  Config as SolanaConfig,
  getSolanaConfig,
} from '../../chains/solana/solana.config';
import { SerumConfig } from './serum.config';
import { default as constants } from './serum.constants';
import {
  convertArrayOfSerumOrdersToMapOfOrders,
  convertMarketBidsAndAsksToOrderBook,
  convertOrderSideToSerumSide,
  convertOrderTypeToSerumType,
  convertSerumMarketToMarket,
  convertSerumOrderToOrder,
  convertToTicker,
} from './serum.convertors';
import {
  getNotNullOrThrowError,
  getRandonBN,
  promiseAllInBatches,
  runWithRetryAndTimeout,
} from './serum.helpers';
import {
  BasicSerumMarket,
  CancelOrderRequest,
  CancelOrdersRequest,
  CreateOrdersRequest,
  Fund,
  FundsSettlementError,
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
  OrderSide,
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

const caches = {
  instances: new CacheContainer(new MemoryStorage()),
  markets: new CacheContainer(new MemoryStorage()),
  serumFindQuoteTokenAccountsForOwner: new CacheContainer(new MemoryStorage()),
  serumFindBaseTokenAccountsForOwner: new CacheContainer(new MemoryStorage()),
};

export type Serumish = Serum;

/**
 * Serum is a wrapper around the Serum  API.
 *
 * // TODO Listen the events from the serum API to automatically settle the funds (specially when filling orders)
 */
export class Serum {
  private initializing: boolean = false;

  private readonly config: SerumConfig.Config;
  private readonly solanaConfig: SolanaConfig;
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

    this.config = SerumConfig.config;
    this.solanaConfig = getSolanaConfig(chain, network);

    this.connection = new Connection(this.solanaConfig.network.nodeUrl);
  }

  private async serumGetMarketsInformation(): Promise<BasicSerumMarket[]> {
    const marketsURL =
      this.config.markets.url ||
      'https://raw.githubusercontent.com/project-serum/serum-ts/master/packages/serum/src/markets.json';

    let marketsInformation: BasicSerumMarket[];

    try {
      marketsInformation = (
        await runWithRetryAndTimeout<any>(axios, axios.get, [marketsURL])
      ).data;
    } catch (e) {
      marketsInformation = MARKETS;
    }

    return marketsInformation;
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
  private async serumLoadMarket(
    connection: Connection,
    address: PublicKey,
    options: SerumMarketOptions | undefined,
    programId: PublicKey,
    layoutOverride?: any
  ): Promise<SerumMarket> {
    return await runWithRetryAndTimeout<Promise<SerumMarket>>(
      SerumMarket,
      SerumMarket.load,
      [
        connection,
        address,
        <SerumMarketOptions>options,
        programId,
        layoutOverride,
      ]
    );
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @private
   */
  private async serumMarketLoadBids(
    market: SerumMarket,
    connection: Connection
  ): Promise<SerumOrderBook> {
    return await runWithRetryAndTimeout<Promise<SerumOrderBook>>(
      market,
      market.loadBids,
      [connection]
    );
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @private
   */
  private async serumMarketLoadAsks(
    market: SerumMarket,
    connection: Connection
  ): Promise<SerumOrderBook> {
    return await runWithRetryAndTimeout<Promise<SerumOrderBook>>(
      market,
      market.loadAsks,
      [connection]
    );
  }

  /**
   * 1 external API call.
   *
   * @param market
   * @param connection
   * @param limit
   * @private
   */
  private async serumMarketLoadFills(
    market: SerumMarket,
    connection: Connection,
    limit?: number
  ): Promise<any[]> {
    return await runWithRetryAndTimeout<Promise<any[]>>(
      market,
      market.loadFills,
      [connection, limit]
    );
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
  private async serumMarketLoadOrdersForOwner(
    market: SerumMarket,
    connection: Connection,
    ownerAddress: PublicKey,
    cacheDurationMs?: number
  ): Promise<SerumOrder[]> {
    return await runWithRetryAndTimeout<Promise<SerumOrder[]>>(
      market,
      market.loadOrdersForOwner,
      [connection, ownerAddress, cacheDurationMs]
    );
  }

  // /**
  //  * 1 external API call.
  //  *
  //  * @param market
  //  * @param connection
  //  * @param owner
  //  * @param payer
  //  * @param side
  //  * @param price
  //  * @param size
  //  * @param orderType
  //  * @param clientId
  //  * @param openOrdersAddressKey
  //  * @param openOrdersAccount
  //  * @param feeDiscountPubkey
  //  * @param maxTs
  //  * @param replaceIfExists
  //  * @private
  //  */
  // private async serumMarketPlaceOrder(
  //   market: SerumMarket,
  //   connection: Connection,
  //   {
  //     owner,
  //     payer,
  //     side,
  //     price,
  //     size,
  //     orderType,
  //     clientId,
  //     openOrdersAddressKey,
  //     openOrdersAccount,
  //     feeDiscountPubkey,
  //     maxTs,
  //     replaceIfExists,
  //   }: SerumOrderParams<Account>
  // ): Promise<TransactionSignature> {
  //   return await runWithRetryAndTimeout<Promise<TransactionSignature>>(
  //     market,
  //     market.placeOrder,
  //     [
  //       connection,
  //       {
  //         owner,
  //         payer,
  //         side,
  //         price,
  //         size,
  //         orderType,
  //         clientId,
  //         openOrdersAddressKey,
  //         openOrdersAccount,
  //         feeDiscountPubkey,
  //         maxTs,
  //         replaceIfExists,
  //       },
  //     ]
  //   );
  // }

  /**
   * Place one or more orders in a single transaction for each owner informed.
   * $numberOfDifferentOwners external API calls.
   *
   * @param market
   * @param connection
   * @param orders
   * @private
   */
  private async serumMarketPlaceOrders(
    market: SerumMarket,
    connection: Connection,
    orders: SerumOrderParams<Account>[]
  ): Promise<TransactionSignature[]> {
    return await runWithRetryAndTimeout<Promise<TransactionSignature[]>>(
      market,
      market.placeOrders,
      [connection, orders]
    );
  }

  // /**
  //  * 1 external API call.
  //  *
  //  * @param market
  //  * @param connection
  //  * @param owner
  //  * @param order
  //  * @private
  //  */
  // private async serumMarketCancelOrder(market: SerumMarket, connection: Connection, owner: Account, order: SerumOrder): Promise<TransactionSignature> {
  //   return await runWithRetryAndTimeout<Promise<TransactionSignature>>(
  //     market,
  //     market.cancelOrder,
  //     [connection, owner, order]
  //   );
  // }

  /**
   * Cancel one or more order in a single transaction.
   * 2 external API call.
   *
   * @param market
   * @param connection
   * @param owner
   * @param orders
   * @private
   */
  private async serumMarketCancelOrdersAndSettleFunds(
    market: SerumMarket,
    connection: Connection,
    owner: Account,
    orders: SerumOrder[]
  ): Promise<{ cancellation: string; fundsSettlement: string }> {
    const cancellationSignature = await runWithRetryAndTimeout<
      Promise<TransactionSignature>
    >(market, market.cancelOrders, [connection, owner, orders]);

    const fundsSettlements: {
      owner: Account;
      openOrders: SerumOpenOrders;
      baseWallet: PublicKey;
      quoteWallet: PublicKey;
      referrerQuoteWallet: PublicKey | null;
    }[] = [];

    for (const openOrders of await this.serumFindOpenOrdersAccountsForOwner(
      market,
      connection,
      owner.publicKey
    )) {
      if (
        openOrders.baseTokenFree.gt(new BN(0)) ||
        openOrders.quoteTokenFree.gt(new BN(0))
      ) {
        const base = await this.serumFindBaseTokenAccountsForOwner(
          market,
          this.connection,
          owner.publicKey,
          true
        );
        const baseWallet = base[0].pubkey;

        const quote = await this.serumFindQuoteTokenAccountsForOwner(
          market,
          this.connection,
          owner.publicKey,
          true
        );
        const quoteWallet = quote[0].pubkey;

        fundsSettlements.push({
          owner,
          openOrders,
          baseWallet,
          quoteWallet,
          referrerQuoteWallet: null,
        });
      }
    }

    try {
      const fundsSettlementSignature = (
        await this.serumSettleSeveralFunds(
          market,
          connection,
          fundsSettlements,
          new Transaction() // There's only one owner.
        )
      )[0]; // There's only one owner.

      return {
        cancellation: cancellationSignature,
        fundsSettlement: fundsSettlementSignature,
      };
    } catch (exception: any) {
      if (
        exception.message.includes('It is unknown if it succeeded or failed.')
      ) {
        throw new FundsSettlementError(
          `Unknown state when settling the funds for the market: ${exception.message}`
        );
      } else {
        throw exception;
      }
    }
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
  private async serumFindOpenOrdersAccountsForOwner(
    market: SerumMarket,
    connection: Connection,
    ownerAddress: PublicKey,
    cacheDurationMs?: number
  ): Promise<SerumOpenOrders[]> {
    return await runWithRetryAndTimeout<Promise<SerumOpenOrders[]>>(
      market,
      market.findOpenOrdersAccountsForOwner,
      [connection, ownerAddress, cacheDurationMs]
    );
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
  private async serumFindBaseTokenAccountsForOwner(
    market: SerumMarket,
    connection: Connection,
    ownerAddress: PublicKey,
    includeUnwrappedSol?: boolean
  ): Promise<Array<{ pubkey: PublicKey; account: AccountInfo<Buffer> }>> {
    return await runWithRetryAndTimeout<
      Promise<Array<{ pubkey: PublicKey; account: AccountInfo<Buffer> }>>
    >(market, market.findBaseTokenAccountsForOwner, [
      connection,
      ownerAddress,
      includeUnwrappedSol,
    ]);
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
  private async serumFindQuoteTokenAccountsForOwner(
    market: SerumMarket,
    connection: Connection,
    ownerAddress: PublicKey,
    includeUnwrappedSol?: boolean
  ): Promise<Array<{ pubkey: PublicKey; account: AccountInfo<Buffer> }>> {
    return await runWithRetryAndTimeout<
      Promise<Array<{ pubkey: PublicKey; account: AccountInfo<Buffer> }>>
    >(market, market.findQuoteTokenAccountsForOwner, [
      connection,
      ownerAddress,
      includeUnwrappedSol,
    ]);
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
  private async serumSettleFunds(
    market: SerumMarket,
    connection: Connection,
    owner: Account,
    openOrders: SerumOpenOrders,
    baseWallet: PublicKey,
    quoteWallet: PublicKey,
    referrerQuoteWallet?: PublicKey | null
  ): Promise<TransactionSignature> {
    return await runWithRetryAndTimeout<Promise<TransactionSignature>>(
      market,
      market.settleFunds,
      [
        connection,
        owner,
        openOrders,
        baseWallet,
        quoteWallet,
        referrerQuoteWallet,
      ]
    );
  }

  /**
   * Settle the funds in a single transaction for each owner.
   * $numberOfDifferentOwners external API calls.
   *
   * @param market
   * @param connection
   * @param settlements
   * @param transaction
   * @private
   */
  private async serumSettleSeveralFunds(
    market: SerumMarket,
    connection: Connection,
    settlements: {
      owner: Account;
      openOrders: SerumOpenOrders;
      baseWallet: PublicKey;
      quoteWallet: PublicKey;
      referrerQuoteWallet: PublicKey | null;
    }[],
    transaction: Transaction = new Transaction()
  ): Promise<TransactionSignature[]> {
    return await runWithRetryAndTimeout<Promise<TransactionSignature[]>>(
      market,
      market.settleSeveralFunds,
      [connection, settlements, transaction]
    );
  }

  private async getSolanaAccount(address: string): Promise<Account> {
    return await runWithRetryAndTimeout<Promise<Account>>(
      this.solana,
      this.solana.getAccount,
      [address]
    );
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
    return new Serum(chain, network);
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

    const getMarket = async (name: string): Promise<void> => {
      const market = await this.getMarket(name);

      markets.set(name, market);
    };

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getMarket, names);

    return markets;
  }

  /**
   * $numberOfAllowedMarkets external API calls.
   */
  @Cache(caches.markets, { ttl: constants.cache.markets })
  async getAllMarkets(): Promise<IMap<string, Market>> {
    const allMarkets = IMap<string, Market>().asMutable();

    let marketsInformation: BasicSerumMarket[] =
      await this.serumGetMarketsInformation();

    marketsInformation = marketsInformation.filter(
      (item) =>
        !item.deprecated &&
        (this.config.markets.blacklist?.length
          ? !this.config.markets.blacklist.includes(item.name)
          : true) &&
        (this.config.markets.whiteList?.length
          ? this.config.markets.whiteList.includes(item.name)
          : true)
    );

    const loadMarket = async (market: BasicSerumMarket): Promise<void> => {
      const serumMarket = await this.serumLoadMarket(
        this.connection,
        new PublicKey(market.address),
        {},
        new PublicKey(market.programId)
      );

      allMarkets.set(
        market.name,
        convertSerumMarketToMarket(serumMarket, market)
      );
    };

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    // It takes on average about 44s to load all the markets
    await promiseAllInBatches(loadMarket, marketsInformation);

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

    return convertMarketBidsAndAsksToOrderBook(market, asks, bids);
  }

  /**
   * 2*$numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   */
  async getOrderBooks(marketNames: string[]): Promise<IMap<string, OrderBook>> {
    const orderBooks = IMap<string, OrderBook>().asMutable();

    const getOrderBook = async (marketName: string): Promise<void> => {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    };

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getOrderBook, marketNames);

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
        const url = (
          this.config.tickers.url ||
          'https://nomics.com/data/exchange-markets-ticker?convert=USD&exchange=serum_dex&interval=1d&market=${marketAddress}'
        ).replace('${marketAddress}', market.address.toString());

        const result: { price: any; last_updated_at: any } = (
          await axios.get(url)
        ).data.items[0];

        return convertToTicker(result);
      }
    } catch (exception) {
      throw new TickerNotFoundError(
        `Ticker data is currently not available for market "${marketName}".`
      );
    }

    throw new TickerNotFoundError(
      `Ticker source (${this.config.tickers.source}) not supported, check your serum configuration file.`
    );

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

    const getTicker = async (marketName: string): Promise<void> => {
      const ticker = await this.getTicker(marketName);

      tickers.set(marketName, ticker);
    };

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(getTicker, marketNames);

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
      throw new OrderNotFoundError(
        `No owner address provided for order "${target.id} / ${target.exchangeId}".`
      );

    if (target.marketName) {
      const openOrder = (
        await this.getOpenOrdersForMarket(
          target.marketName,
          target.ownerAddress
        )
      ).find(
        (order) =>
          order.id === target.id || order.exchangeId === target.exchangeId
      );

      if (!openOrder)
        throw new OrderNotFoundError(
          `No open order found with id / exchange id "${target.id} / ${target.exchangeId}".`
        );

      openOrder.status = OrderStatus.OPEN;

      return openOrder;
    }

    const mapOfOpenOrdersForMarkets = await this.getAllOpenOrders(
      target.ownerAddress
    );

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

    throw new OrderNotFoundError(
      `No open order found with id / exchange id "${target.id} / ${target.exchangeId}".`
    );
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
    const temporary = IMap<string, Order>().asMutable();

    const getOrders = async (target: GetOrdersRequest) => {
      if (target.marketName) {
        temporary.concat(
          await this.getOpenOrdersForMarket(
            target.marketName,
            target.ownerAddress
          )
        );
      } else {
        (await this.getAllOpenOrders(target.ownerAddress)).reduce(
          (acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
            return acc.concat(mapOfOrders);
          },
          temporary
        );
      }
    };

    await promiseAllInBatches(getOrders, targets);

    for (const target of targets) {
      orders.concat(
        temporary.filter((order: Order) => {
          return (
            order.ownerAddress === target.ownerAddress &&
            (target.marketName
              ? order.marketName === target.marketName
              : true) &&
            (target.ids?.length || target.exchangeIds?.length
              ? target.ids?.includes(<string>order.id) ||
                target.exchangeIds?.includes(<string>order.exchangeId)
              : true)
          );
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

    const owner = await this.getSolanaAccount(ownerAddress);

    const serumOpenOrders = await this.serumMarketLoadOrdersForOwner(
      market.market,
      this.connection,
      owner.publicKey
    );

    return convertArrayOfSerumOrdersToMapOfOrders(
      market,
      serumOpenOrders,
      ownerAddress,
      OrderStatus.OPEN
    );
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
      result.set(
        market.name,
        await this.getOpenOrdersForMarket(market.name, ownerAddress)
      );
    };

    await promiseAllInBatches<Market, Promise<void>>(
      getOpenOrders,
      Array.from(markets.values())
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
      throw new OrderNotFoundError(
        `No owner address provided for order "${target.id} / ${target.exchangeId}".`
      );

    if (target.marketName) {
      const filledOrder = (
        await this.getFilledOrdersForMarket(target.marketName)
      ).find(
        (order) =>
          order.id === target.id || order.exchangeId === target.exchangeId
      );

      if (!filledOrder)
        throw new OrderNotFoundError(
          `No open order found with id / exchange id "${target.id} / ${target.exchangeId}".`
        );

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

    throw new OrderNotFoundError(
      `No filled order found with id / exchange id "${target.id} / ${target.exchangeId}".`
    );
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
    const temporary = IMap<string, Order>().asMutable();

    const getOrders = async (target: GetOrdersRequest) => {
      if (target.marketName) {
        temporary.concat(
          await this.getFilledOrdersForMarket(target.marketName)
        );
      } else {
        (await this.getAllFilledOrders()).reduce(
          (acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
            return acc.concat(mapOfOrders);
          },
          temporary
        );
      }
    };

    await promiseAllInBatches(getOrders, targets);

    for (const target of targets) {
      orders.concat(
        temporary.filter((order: Order) => {
          return (
            order.ownerAddress === target.ownerAddress &&
            (target.marketName
              ? order.marketName === target.marketName
              : true) &&
            (target.ids?.length || target.exchangeIds?.length
              ? target.ids?.includes(<string>order.id) ||
                target.exchangeIds?.includes(<string>order.exchangeId)
              : true)
          );
        })
      );
    }

    if (!orders.size) throw new OrderNotFoundError('No filled orders found.');

    return orders;
  }

  /**
   * 1 external API calls.
   *
   * @param marketName
   */
  async getFilledOrdersForMarket(
    marketName: string
  ): Promise<IMap<string, Order>> {
    const market = await this.getMarket(marketName);

    const orders = await this.serumMarketLoadFills(
      market.market,
      this.connection,
      0
    );

    // TODO check if it's possible to get the owner address
    return convertArrayOfSerumOrdersToMapOfOrders(
      market,
      orders,
      undefined,
      OrderStatus.FILLED
    );
  }

  /**
   * $numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   */
  async getFilledOrdersForMarkets(
    marketNames: string[]
  ): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    const markets = await this.getMarkets(marketNames);

    const getFilledOrders = async (market: Market): Promise<void> => {
      result.set(market.name, await this.getFilledOrdersForMarket(market.name));
    };

    await promiseAllInBatches<Market, Promise<void>>(
      getFilledOrders,
      Array.from(markets.values())
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
            throw new OrderNotFoundError(
              `No order found with id / exchange id "${target.id} / ${target.exchangeId}".`
            );
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
    const temporary = IMap<string, Order>().asMutable();

    const getOrders = async (target: GetOrdersRequest) => {
      if (target.marketName) {
        const openOrders = await this.getOpenOrdersForMarket(
          target.marketName,
          target.ownerAddress
        );
        const filledOrders = await this.getFilledOrdersForMarket(
          target.marketName
        );
        temporary.concat(openOrders).concat(filledOrders);
      } else {
        (await this.getAllOpenOrders(target.ownerAddress)).reduce(
          (acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
            return acc.concat(mapOfOrders);
          },
          temporary
        );

        (await this.getAllFilledOrders()).reduce(
          (acc: IMap<string, Order>, mapOfOrders: IMap<string, Order>) => {
            return acc.concat(mapOfOrders);
          },
          temporary
        );
      }
    };

    await promiseAllInBatches(getOrders, targets);

    for (const target of targets) {
      orders.concat(
        temporary.filter((order: Order) => {
          return (
            order.ownerAddress === target.ownerAddress &&
            (target.marketName
              ? order.marketName === target.marketName
              : true) &&
            (target.ids?.length || target.exchangeIds?.length
              ? target.ids?.includes(<string>order.id) ||
                target.exchangeIds?.includes(<string>order.exchangeId)
              : true)
          );
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
  async getOrdersForMarket(
    marketName: string,
    ownerAddress: string
  ): Promise<IMap<string, Order>> {
    const orders = await this.getOpenOrdersForMarket(marketName, ownerAddress);
    orders.concat(await this.getFilledOrdersForMarket(marketName));

    return orders;
  }

  /**
   * 2*$numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   * @param ownerAddress
   */
  async getOrdersForMarkets(
    marketNames: string[],
    ownerAddress: string
  ): Promise<IMap<string, IMap<string, Order>>> {
    const result = IMap<string, IMap<string, Order>>().asMutable();

    const markets = await this.getMarkets(marketNames);

    const getOrders = async (market: Market): Promise<void> => {
      result.set(
        market.name,
        await this.getOrdersForMarket(market.name, ownerAddress)
      );
    };

    await promiseAllInBatches<Market, Promise<void>>(
      getOrders,
      Array.from(markets.values())
    );

    return result;
  }

  /**
   * 2*$numberOfAllMarkets external API calls.
   *
   * @param ownerAddress
   */
  async getAllOrders(
    ownerAddress: string
  ): Promise<IMap<string, IMap<string, Order>>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return await this.getOrdersForMarkets(marketNames, ownerAddress);
  }

  /**
   * 1 external API call.
   *
   * @param candidate
   */
  async createOrder(candidate: CreateOrdersRequest): Promise<Order> {
    return (await this.createOrders([candidate])).first();
  }

  /**
   * $numberOfDifferentOwners*$numberOfAllowedMarkets external API calls.
   *
   * @param candidates
   */
  async createOrders(
    candidates: CreateOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    // TODO Check the maximum number of orders that we can create at once

    const ordersMap = IMap<
      Market,
      IMap<
        Account,
        { request: CreateOrdersRequest; serum: SerumOrderParams<Account> }[]
      >
    >().asMutable();

    for (const candidate of candidates) {
      const market = await this.getMarket(candidate.marketName);

      let marketMap = ordersMap.get(market);
      if (!marketMap) {
        marketMap = IMap<
          Account,
          { request: CreateOrdersRequest; serum: SerumOrderParams<Account> }[]
        >().asMutable();
        ordersMap.set(market, getNotNullOrThrowError(marketMap));
      }

      const owner = await this.getSolanaAccount(candidate.ownerAddress);

      let ownerOrders = marketMap?.get(owner);
      if (!ownerOrders) {
        ownerOrders = [];
        marketMap?.set(owner, ownerOrders);
      }

      let payer: PublicKey;
      if (candidate.payerAddress) {
        payer = new PublicKey(candidate.payerAddress);
      } else {
        if (candidate.side == OrderSide.SELL) {
          // It's the same as the owner wallet address.

          payer = new PublicKey(getNotNullOrThrowError(candidate.payerAddress));
        } else if (candidate.side == OrderSide.BUY) {
          // It's the token account address for the quote asset.

          const quoteToken = candidate.marketName.split('/')[1];
          const keypair = await this.solana.getKeypair(candidate.ownerAddress);
          const tokenInfo: TokenInfo = getNotNullOrThrowError(
            this.solana.getTokenForSymbol(quoteToken)
          );
          const mintAddress = new PublicKey(tokenInfo.address);
          const account = await runWithRetryAndTimeout(
            this.solana,
            this.solana.getOrCreateAssociatedTokenAccount,
            [keypair, mintAddress]
          );

          payer = getNotNullOrThrowError<TokenAccount>(account).address;
        } else {
          throw new Error(`Invalid order side: ${candidate.side}`);
        }
      }

      const candidateSerumOrder: SerumOrderParams<Account> = {
        side: convertOrderSideToSerumSide(candidate.side),
        price: candidate.price,
        size: candidate.amount,
        orderType: convertOrderTypeToSerumType(candidate.type),
        clientId: candidate.id ? new BN(candidate.id) : getRandonBN(),
        owner: owner,
        payer: payer,
      };

      ownerOrders.push({ request: candidate, serum: candidateSerumOrder });
    }

    const createdOrders = IMap<string, Order>().asMutable();
    for (const [market, marketMap] of ordersMap.entries()) {
      for (const [owner, orders] of marketMap.entries()) {
        let status: OrderStatus;
        let signatures: TransactionSignature[];
        try {
          signatures = await this.serumMarketPlaceOrders(
            market.market,
            this.connection,
            orders.map((order) => order.serum)
          );

          status = OrderStatus.OPEN;
        } catch (exception: any) {
          if (
            exception.message.includes(
              'It is unknown if it succeeded or failed.'
            )
          ) {
            signatures = [];
            status = OrderStatus.CREATION_PENDING;
          } else {
            throw exception;
          }
        }

        for (const order of orders) {
          createdOrders.set(
            getNotNullOrThrowError(
              order.serum.clientId?.toString(),
              'Client id is not defined.'
            ),
            convertSerumOrderToOrder(
              market,
              undefined,
              order.request,
              order.serum,
              owner.publicKey.toString(),
              status,
              signatures[0]
            )
          );
        }
      }
    }

    return createdOrders;
  }

  /**
   * (4 + $numberOfOpenAccountsForOwner) or (3 + $numberOfAllowedMarkets + $numberOfOpenAccountsForOwner) external API calls.
   *
   * @param target
   */
  async cancelOrder(target: CancelOrderRequest): Promise<Order> {
    const market = await this.getMarket(target.marketName);

    const owner = await this.getSolanaAccount(target.ownerAddress);

    const order = await this.getOpenOrder({ ...target });

    try {
      order.signature = (
        await this.serumMarketCancelOrdersAndSettleFunds(
          market.market,
          this.connection,
          owner,
          [getNotNullOrThrowError(order.order)]
        )
      ).cancellation;

      order.status = OrderStatus.CANCELED;

      return order;
    } catch (exception: any) {
      if (
        exception.message.includes('It is unknown if it succeeded or failed.')
      ) {
        order.status = OrderStatus.CANCELATION_PENDING;

        return order;
      } else {
        throw exception;
      }
    }
  }

  /**
   * $numberOfTargets + $numberOfDifferentMarkets*$numberOfDifferentOwnersForEachMarket external API calls.
   *
   * @param targets
   */
  async cancelOrders(
    targets: CancelOrdersRequest[]
  ): Promise<IMap<string, Order>> {
    const ordersMap = IMap<Market, IMap<Account, Order[]>>().asMutable();

    for (const target of targets) {
      const market = await this.getMarket(target.marketName);

      // TODO tune this method in order to call less the below operation.
      const openOrders = await this.getOpenOrders([{ ...target }]);

      let marketMap = ordersMap.get(market);
      if (!marketMap) {
        marketMap = IMap<Account, Order[]>().asMutable();
        ordersMap.set(market, getNotNullOrThrowError(marketMap));
      }

      const owner = await this.getSolanaAccount(target.ownerAddress);

      let ownerOrders = marketMap?.get(owner);
      if (!ownerOrders) {
        ownerOrders = [];
        marketMap?.set(owner, ownerOrders);
      }

      ownerOrders.push(...openOrders.values());
    }

    const canceledOrders = IMap<string, Order>().asMutable();
    for (const [market, marketMap] of ordersMap.entries()) {
      for (const [owner, orders] of marketMap.entries()) {
        const serumOrders = orders.map((order) =>
          getNotNullOrThrowError(order.order)
        ) as SerumOrder[];

        if (!serumOrders.length) continue;

        let status: OrderStatus;
        let signature: TransactionSignature;
        try {
          signature = (
            await this.serumMarketCancelOrdersAndSettleFunds(
              market.market,
              this.connection,
              owner,
              serumOrders
            )
          ).cancellation;

          status = OrderStatus.CANCELED;
        } catch (exception: any) {
          if (
            exception.message.includes(
              'It is unknown if it succeeded or failed.'
            )
          ) {
            signature = '';
            status = OrderStatus.CANCELATION_PENDING;
          } else {
            throw exception;
          }
        }

        if (orders.length) {
          for (const order of orders) {
            order.status = status;
            order.signature = signature;
            canceledOrders.set(
              getNotNullOrThrowError(
                order.order?.clientId?.toString(),
                'Client id is not defined.'
              ),
              order
            );
          }
        }
      }
    }

    return canceledOrders;
  }

  /**
   * $numberOfOpenOrders external API calls.
   *
   * @param ownerAddress
   */
  async cancelAllOrders(ownerAddress: string): Promise<IMap<string, Order>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    const requests: CancelOrdersRequest[] = marketNames.map((marketName) => ({
      marketName,
      ownerAddress,
    }));

    return this.cancelOrders(requests);
  }

  /**
   * 3*$numberOfOpenOrdersAccountsForMarket external API calls.
   *
   * @param marketName
   * @param ownerAddress
   */
  async settleFundsForMarket(
    marketName: string,
    ownerAddress: string
  ): Promise<TransactionSignature[]> {
    const market = await this.getMarket(marketName);
    const owner = await this.getSolanaAccount(ownerAddress);
    const signatures: TransactionSignature[] = [];

    // const fundsSettlements: {
    //   owner: Account,
    //   openOrders: SerumOpenOrders,
    //   baseWallet: PublicKey,
    //   quoteWallet: PublicKey,
    //   referrerQuoteWallet: PublicKey | null
    // }[] = [];

    for (const openOrders of await this.serumFindOpenOrdersAccountsForOwner(
      market.market,
      this.connection,
      owner.publicKey
    )) {
      if (
        openOrders.baseTokenFree.gt(new BN(0)) ||
        openOrders.quoteTokenFree.gt(new BN(0))
      ) {
        const base = await this.serumFindBaseTokenAccountsForOwner(
          market.market,
          this.connection,
          owner.publicKey,
          true
        );
        const baseWallet = base[0].pubkey;

        const quote = await this.serumFindQuoteTokenAccountsForOwner(
          market.market,
          this.connection,
          owner.publicKey,
          true
        );
        const quoteWallet = quote[0].pubkey;

        try {
          signatures.push(
            await this.serumSettleFunds(
              market.market,
              this.connection,
              owner,
              openOrders,
              baseWallet,
              quoteWallet,
              null
            )
          );
        } catch (exception: any) {
          if (
            exception.message.includes(
              'It is unknown if it succeeded or failed.'
            )
          ) {
            throw new FundsSettlementError(
              `Unknown state when settling the funds for the market "${marketName}": ${exception.message}`
            );
          } else {
            throw exception;
          }
        }

        // fundsSettlements.push({
        //   owner,
        //   openOrders,
        //   baseWallet,
        //   quoteWallet,
        //   referrerQuoteWallet: null
        // });
      }
    }

    // try {
    //   return await this.serumSettleSeveralFunds(
    //     market.market,
    //     this.connection,
    //     fundsSettlements
    //   );
    // } catch (exception: any) {
    //   if (exception.message.includes('It is unknown if it succeeded or failed.')) {
    //     throw new FundsSettlementError(`Unknown state when settling the funds for the market "${marketName}": ${exception.message}`);
    //   } else {
    //     throw exception;
    //   }
    // }

    return signatures;
  }

  /**
   * 3*$numberOfOpenOrdersAccountsForMarket*$numberOfInformedMarkets external API calls.
   *
   * @param marketNames
   * @param ownerAddress
   */
  async settleFundsForMarkets(
    marketNames: string[],
    ownerAddress: string
  ): Promise<IMap<string, Fund[]>> {
    const funds = IMap<string, Fund[]>().asMutable();

    const settleFunds = async (marketName: string): Promise<void> => {
      const signatures = await this.settleFundsForMarket(
        marketName,
        ownerAddress
      );

      funds.set(marketName, signatures);
    };

    // The rate limits are defined here: https://docs.solana.com/cluster/rpc-endpoints
    await promiseAllInBatches(settleFunds, marketNames);

    return funds;
  }

  /**
   * 3*$numberOfOpenOrdersAccountsForMarket*$numberOfAllowedMarkets external API calls.
   *
   * @param ownerAddress
   */
  async settleAllFunds(ownerAddress: string): Promise<IMap<string, Fund[]>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.settleFundsForMarkets(marketNames, ownerAddress);
  }
}
