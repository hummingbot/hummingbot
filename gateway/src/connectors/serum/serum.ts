import { Account, Connection, PublicKey } from '@solana/web3.js';
import { Market as SerumMarket, MARKETS } from '@project-serum/serum';
import {} from '@solana/spl-token';
import { Solana } from '../../chains/solana/solana';
import { SerumConfig } from './serum.config';
import {Market} from "./serum.types";

export type Serumish = Serum;

export class Serum {
  private static instances: { [name: string]: Serum };

  private ready: boolean = false;
  private initializing: boolean = false;

  private tokens: string[] = ['ABC', 'SOL'];
  private markets: Map<string, Market>;

  private chain: string;
  private solana: Solana;
  private connection: Connection;

  private async loadTokens() {
    return this.tokens;
  }

  private constructor(chain: string, network: string) {
    this.chain = chain;
    this.solana = Solana.getInstance(network);

    const config = SerumConfig.config;

    this.connection = new Connection(config.network.rpcUrl);
  }

  static getInstance(chain: string, network: string): Serum {
    if (Serum.instances === undefined) {
      Serum.instances = {};
    }
    if (!(chain + network in Serum.instances)) {
      Serum.instances[chain + network] = new Serum(chain, network);
    }

    return Serum.instances[chain + network];
  }

  static reload(chain: string, network: string): Serum {
    Serum.instances[chain + network] = new Serum(chain, network);

    return Serum.instances[chain + network];
  }

  async init() {
    if (!this.ready && !this.initializing) {
      this.initializing = true;

      await this.loadTokens();
      this.markets = await this.getAllMarkets();

      this.ready = true;
      this.initializing = false;
    }
  }

  async getMarket(name: string): Promise<Market | undefined> {
    const markets = await this.getAllMarkets();

    return markets.get(name);
  }

  async getMarkets(names: string[]): Promise<Market[]> {

  }

  async getAllMarkets(): Promise<Map<string, Market>> {
    if (this.markets && this.markets.size) return this.markets;

    const markets = new Map<string, Market>();

    for (const market of MARKETS) {
      markets.set(market.name, {
        ...market,
        market: await SerumMarket.load(
          this.connection,
          market.address,
          {},
          market.programId
        ),
      });
    }

    this.markets = markets;

    return this.markets;
  }

  async getOrderBook(): Promise<any> {

  }

  async getOrderBooks(): Promise<any> {

  }

  async getAllOrderBooks(): Promise<any> {
  }

  async getTicker(): Promise<any> {

  }

  async getTickers(): Promise<any> {

  }

  async getAllTickers(): Promise<any> {
  }

  async getOrder(): Promise<any> {

  }

  async getOrders(): Promise<any> {

  }

  async getAllOrders(): Promise<any> {
  }

  async createOrder(): Promise<any> {

  }

  async createOrders(): Promise<any> {

  }

  async updateOrder(): Promise<any> {
  }

  async updateOrders(): Promise<any> {
  }

  async deleteOrder(): Promise<any> {
  }

  async deleteOrders(): Promise<any> {
  }

  async getOpenOrder(): Promise<any> {
  }

  async getOpenOrders(): Promise<any> {
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

  async getFilledOrders(): Promise<any> {
  }

  async getAllFilledOrders(): Promise<any> {
  }
}
