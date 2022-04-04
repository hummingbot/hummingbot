import { Account, Keypair, Connection } from '@solana/web3.js';
import {
  Market as SerumMarket,
  Orderbook as SerumOrderBook,
  MARKETS,
} from '@project-serum/serum';
import { Solana } from '../../chains/solana/solana';
import { SerumConfig } from './serum.config';
import {Market, Order, OrderBook, CandidateOrder} from './serum.types';
import BN from 'bn.js';
import { OrderParams as SerumOrderParams } from "@project-serum/serum/lib/market";

export type Serumish = Serum;

export class Serum {
  private static instances: { [name: string]: Serum };

  private initializing: boolean = false;

  private tokens: string[] = ['ABC', 'SOL'];
  private markets: Map<string, Market | null> = new Map();

  private config;
  private solana: Solana;
  private connection: Connection;
  private owner: Keypair;
  private ownerAccount: Account;

  ready: boolean = false;
  chain: string;
  network: string;

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

  private parseToMarket(
    info: Record<string, unknown>,
    market: SerumMarket | undefined | null
  ): Market | null {
    if (!market) return null;

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

  /**
   * Initialize the Serum instance.
   */
  async init() {
    if (!this.ready && !this.initializing) {
      this.initializing = true;

      this.solana = Solana.getInstance(this.network);
      this.connection = new Connection(this.config.network.rpcUrl);

      this.owner = new Keypair(this.config.accounts.owner.privateKey);
      this.ownerAccount = new Account(this.owner.publicKey.toBuffer());

      this.markets = await this.getAllMarkets();

      this.ready = true;
      this.initializing = false;
    }
  }

  /**
   *
   * @param name
   */
  async getMarket(name: string): Promise<Market | null> {
    const markets = await this.getAllMarkets();

    return markets.get(name) || null;
  }

  /**
   *
   * @param names
   */
  async getMarkets(names: string[]): Promise<Map<string, Market | null>> {
    const allMarkets = await this.getAllMarkets();

    const markets = new Map<string, Market | null>();

    for (const name of names) {
      const market = allMarkets.get(name) || null;

      markets.set(name, market);
    }

    return markets;
  }

  /**
   *
   */
  async getAllMarkets(): Promise<Map<string, Market | null>> {
    if (this.markets && this.markets.size) return this.markets;

    const allMarkets = new Map<string, Market | null>();

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

    this.markets = allMarkets;

    return this.markets;
  }

  async getOrderBook(marketName: string): Promise<OrderBook | null> {
    const market = await this.getMarket(marketName);

    if (!market) return null;

    return this.parseToOrderBook(
      await market.market.loadAsks(this.connection),
      await market.market.loadBids(this.connection)
    );
  }

  async getOrderBooks(
    marketNames: string[]
  ): Promise<Map<string, OrderBook | null>> {
    const orderBooks = new Map<string, OrderBook | null>();

    for (const marketName of marketNames) {
      const orderBook = await this.getOrderBook(marketName);

      orderBooks.set(marketName, orderBook);
    }

    return orderBooks;
  }

  async getAllOrderBooks(): Promise<Map<string, OrderBook | null>> {
    const marketNames = Array.from((await this.getAllMarkets()).keys());

    return this.getOrderBooks(marketNames);
  }

  async getTicker(): Promise<any> {

  }

  async getTickers(): Promise<any> {

  }

  async getAllTickers(): Promise<any> {
  }

  async getOrder(): Promise<Order | null> {

  }

  async getOrders(): Promise<Map<BN, Order>> {

  }

  async getAllOrders(): Promise<Map<BN, Order>> {
  }

  async createOrder(candidateOrder: CandidateOrder): Promise<Order> {
    const market = await this.getMarket(candidateOrder.marketName);

    if (!market)
      throw new Error(`Market ${candidateOrder.marketName} not found.`);

    const serumOrderParams: SerumOrderParams<Account> = {
      ...candidateOrder,
      owner: this.ownerAccount,
      payer: this.owner.publicKey,
    };

    const signature = await market.market.placeOrder(
      this.connection,
      serumOrderParams
    );

    return this.parseToOrder({
      ...candidateOrder,
      signature: signature,
    });
  }

  async createOrders(candidateOrders: CandidateOrder[]): Promise<Order[]> {
    const orders = [];
    for (const candidateOrder of candidateOrders) {
      const order = await this.createOrder(candidateOrder);

      orders.push(order);
    }

    return orders;
  }

  async deleteOrder(): Promise<any> {
    await market.cancelOrder(connection, owner, order);
  }

  async deleteOrders(): Promise<any> {
    const canceledOrders = [];
    for (const candidateOrder of candidateOrders) {
      const order = await this.createOrder(candidateOrder);

      canceledOrders.push(order);
    }

    return canceledOrders;
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

  async getFilledOrder(): Promise<Order | undefined> {
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

    if (!markets || !markets.size) return;

    const result = new Map<string, Order[] | undefined>();

    for (const [marketName, market] of markets) {
      const orders = await market?.market.loadFills(this.connection);

      if (orders) result.set(marketName, this.parseToOrders(orders));
      else result.set(marketName, undefined);
    }

    return result;
  }

  async getAllFilledOrders(): Promise<
    Map<string, Order[] | undefined> | undefined
  > {
    return this.getFilledOrders();
  }
}
