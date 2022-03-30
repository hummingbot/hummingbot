import { Account, Connection, PublicKey } from '@solana/web3.js';
import { Market } from '@project-serum/serum';
import {} from '@solana/spl-token';
import {getMarkets} from "./serum.controllers";

export type Serumish = Serum;

export class Serum {
  private static _instance: Serum;
  private _ready: boolean = false;
  private _initializing: boolean = false;
  private _initPromise: Promise<void> = Promise.resolve();

  private _tokens: string[] = ['ABC', 'SOL'];
  private connection: Connection;

  private async loadTokens() {
    return this._tokens;
  }

  static getInstance(chain: string, network: string): Serum {
    if (!Serum._instance) {
      Serum._instance = new Serum();
    }

    return Serum._instance;
  }

  static reload(): Serum {
    Serum._instance = new Serum();
    return Serum._instance;
  }

  async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      this._initPromise = this.loadTokens().then(() => {
        this._ready = true;
        this._initializing = false;
      });
    }
    return this._initPromise;
  }

  ready(): boolean {
    return this._ready;
  }

  async getMarket(): Promise<Market> {
    await Market.load(this.connection, )
  }

  async getMarkets(): Promise<any> {

  }

  async getAllMarkets(): Promise<any> {
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
