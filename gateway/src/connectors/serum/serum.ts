import {Connection} from '@solana/web3.js';
import {
  Market as SerumMarket,
  Orderbook as SerumOrderBook,
  MARKETS,
} from '@project-serum/serum';
import { Order as SerumOrder } from '@project-serum/serum/lib/market';
import { Solana } from '../../chains/solana/solana';
import { SerumConfig } from './serum.config';
import { Market, Order, OrderBook } from './serum.types';

export type Serumish = Serum;

export class Serum {
  private static instances: { [name: string]: Serum };

  private initializing: boolean = false;

  private tokens: string[] = ['ABC', 'SOL'];
  private markets: Map<string, Market | undefined> = new Map();

  private config;
  private solana: Solana;
  private connection: Connection;

  ready: boolean = false;
  chain: string;
  network: string;

  private async loadTokens() {
    return this.tokens;
  }

  /**
   *
   * @param chain
   * @param config
   */
  private constructor(chain?: string, network?: string) {
    this.config = SerumConfig.config;

    this.chain = chain || this.config.chain;
    this.network = network || this.network.slug;
  }

  /**
   * Get the Serum instance for the given chain and network
   *
   * @param chain
   * @param network
   */
  static getInstance(chain?: string, network?: string): Serum {
    if (!Serum.instances) Serum.instances = {};

    if (!chain) chain = SerumConfig.config.chain;
    if (!network) network = SerumConfig.config.network.slug;

    if (!(`${chain}:${network}` in Serum.instances)) {
      Serum.instances[`${chain}:${network}`] = new Serum(chain, network);
    }

    return Serum.instances[`${chain}:${network}`];
  }

  /**
   * Reload the Serum instance for the given chain and network
   *
   * @param chain
   * @param network
   */
  static reload(chain: string, network: string): Serum {
    Serum.instances[`${chain}:${network}`] = new Serum(chain, network);

    return Serum.instances[`${chain}:${network}`];
  }

  private convertMarket(
    info: Record<string, unknown>,
    market: SerumMarket | undefined
  ): Market | undefined {
    if (!market) return;

    return {
      ...info,
      market: market,
    } as Market;
  }

  private convertOrderBook(
    asks: SerumOrderBook,
    bids: SerumOrderBook
  ): OrderBook {
    return {
      asks: this.convertOrders(asks),
      bids: this.convertOrders(bids),
      orderBook: {
        asks: asks,
        bids: bids,
      },
    } as OrderBook;
  }

  private convertOrder(order: SerumOrder | Record<string, unknown>): Order {
    // TODO convert the loadFills return too!!!
    return {
      ...order,
      order: order,
    } as Order;
  }

  private convertOrders(
    orders: SerumOrder[] | SerumOrderBook | any[]
  ): Order[] {
    const result = [];

    for (const order of orders) {
      result.push(this.convertOrder(order));
    }

    return result;
  }

  /**
   * Initialize the Serum instance.
   */
  async init() {
    if (!this.ready && !this.initializing) {
      this.initializing = true;

      this.solana = Solana.getInstance(this.network);
      this.connection = new Connection(this.config.network.rpcUrl);

      await this.loadTokens();
      this.markets = await this.getAllMarkets();

      this.ready = true;
      this.initializing = false;
    }
  }

  /**
   *
   * @param name
   */
  async getMarket(name: string): Promise<Market | undefined> {
    const markets = await this.getAllMarkets();

    return markets.get(name);
  }

  /**
   *
   * @param names
   */
  async getMarkets(names: string[]): Promise<Map<string, Market | undefined>> {
    const allMarkets = await this.getAllMarkets();

    const markets = new Map<string, Market | undefined>();

    for (const name of names) {
      const market = allMarkets.get(name);

      markets.set(name, market);
    }

    return markets;
  }

  /**
   *
   */
  async getAllMarkets(): Promise<Map<string, Market | undefined>> {
    if (this.markets && this.markets.size) return this.markets;

    const allMarkets = new Map<string, Market | undefined>();

    for (const market of MARKETS) {
      allMarkets.set(
        market.name,
        this.convertMarket(
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

    this.markets = allMarkets;

    return this.markets;
  }

  async getOrderBook(marketName: string): Promise<OrderBook | undefined> {
    const market = await this.getMarket(marketName);

    if (!market) return;

    return this.convertOrderBook(
      await market.market.loadAsks(this.connection),
      await market.market.loadBids(this.connection)
    );
  }

  async getOrderBooks(
    marketNames: string[]
  ): Promise<Map<string, OrderBook | undefined>> {
    const orderBooks = new Map<string, OrderBook | undefined>();

    for (const marketName of marketNames) {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    return orderBooks;
  }

  async getAllOrderBooks(): Promise<Map<string, OrderBook | undefined>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.getOrderBooks(marketNames);
  }

  async getTicker(): Promise<any> {

  }

  async getTickers(): Promise<any> {

  }

  async getAllTickers(): Promise<any> {
  }

  async getOrder(): Promise<Order | undefined> {

  }

  async getOrders(): Promise<Map<BN, Order>> {

  }

  async getAllOrders(): Promise<Map<BN, Order>> {
  }

  async createOrder(): Promise<any> {
    // Placing orders
    let owner = new Account('...');
    let payer = new PublicKey('...'); // spl-token account
    await market.placeOrder(connection, {
      owner,
      payer,
      side: 'buy', // 'buy' or 'sell'
      price: 123.45,
      size: 17.0,
      orderType: 'limit', // 'limit', 'ioc', 'postOnly'
    });
  }

  async createOrders(): Promise<any> {

  }

  async deleteOrder(): Promise<any> {
    await market.cancelOrder(connection, owner, order);
  }

  async deleteOrders(): Promise<any> {
  }

  async getOpenOrder(): Promise<any> {
  }

  async getOpenOrders(): Promise<any> {
    await market.loadOrdersForOwner(connection, owner.publicKey);
  }

  async getAllOpenOrders(): Promise<any> {
  }

  async deleteOpenOrder(): Promise<any> {
  }

  async deleteOpenOrders(): Promise<any> {
  }

  async deleteAllOpenOrders(): Promise<any> {
  }

  async getFilledOrder(): Promise<any> {
  }

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

    if (!markets) return;

    const result = new Map<string, Order[] | undefined>();

    for (const [marketName, market] of markets) {
      const orders = (await market?.market.loadFills(
        this.connection
      ));

      result.set(marketName, this.convertOrders(orders));
    }

    return result;
  }

  async getAllFilledOrders(): Promise<
    Map<string, Order[] | undefined> | undefined
  > {
    return this.getFilledOrders();
  }
}
