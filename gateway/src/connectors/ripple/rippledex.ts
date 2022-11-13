// import { RippleDEXConfig } from './rippledex.config';
import {
  Config as RippleConfig,
  getRippleConfig,
} from '../../chains/ripple/ripple.config';
import { Ripple } from '../../chains/ripple/ripple';
import { Client, OfferCancel, Transaction, xrpToDrops } from 'xrpl';

export type RippleDEXish = RippleDEX;

export class RippleDEX {
  private static _instances: { [name: string]: RippleDEX };
  // private initializing: boolean = false;

  // private readonly config: RippleDEXConfig.Config;
  private readonly rippleConfig: RippleConfig;
  private readonly client: Client;
  // private ripple!: Ripple;
  private _ready: boolean = false;

  chain: string;
  network: string;
  readonly connector: string = 'rippleDEX';

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

    // this.config = RippleDEXConfig.config;
    this.rippleConfig = getRippleConfig(chain, network);

    this.client = new Client(this.rippleConfig.network.nodeUrl, {
      timeout: this.rippleConfig.requestTimeout,
      connectionTimeout: this.rippleConfig.connectionTimeout,
      feeCushion: this.rippleConfig.feeCushion,
      maxFeeXRP: this.rippleConfig.maxFeeXRP,
    });
  }

  public static getInstance(chain: string, network: string): RippleDEX {
    if (RippleDEX._instances === undefined) {
      RippleDEX._instances = {};
    }
    if (!(network in RippleDEX._instances)) {
      RippleDEX._instances[network] = new RippleDEX(chain, network);
    }

    return RippleDEX._instances[network];
  }

  async getTicker(base: any, quote: any): Promise<any> {
    await this.client.connect();

    const orderbook_resp_ask: any = await this.client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: base,
      taker_pays: quote,
      limit: 1,
    });

    const orderbook_resp_bid: any = await this.client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: quote,
      taker_pays: base,
      limit: 1,
    });

    await this.client.disconnect();

    const asks = orderbook_resp_ask.result.offers;
    const bids = orderbook_resp_bid.result.offers;

    const top_ask = asks[0].quality / 1000000; // TODO: this is for XRP since it is in drop unit, make case for other currency
    const top_bid = 1 / bids[0].quality / 1000000; // TODO: this is for XRP since it is in drop unit, make case for other currency

    const mid_price = (top_ask + top_bid) / 2;

    return {
      mid_price: mid_price,
      timestamp: Date.now(),
    };
  }

  async getOrderBooks(base: any, quote: any, limit: number): Promise<any> {
    await this.client.connect();

    const orderbook_resp_ask: any = await this.client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: base,
      taker_pays: quote,
      limit: limit,
    });

    const orderbook_resp_bid: any = await this.client.request({
      command: 'book_offers',
      ledger_index: 'validated',
      taker_gets: quote,
      taker_pays: base,
      limit: limit,
    });

    await this.client.disconnect();

    const asks = orderbook_resp_ask.result.offers;
    const bids = orderbook_resp_bid.result.offers;

    const top_ask = asks[0].quality / 1000000;
    const top_bid = 1 / bids[0].quality / 1000000;

    const mid_price = (top_ask + top_bid) / 2;

    return {
      base,
      quote,
      asks,
      bids,
      top_ask,
      top_bid,
      mid_price,
      timestamp: Date.now(),
    };
  }

  async getOrders(tx: string): Promise<any> {
    await this.client.connect();

    const tx_resp = await this.client.request({
      command: 'tx',
      transaction: tx,
      binary: false,
    });

    await this.client.disconnect();

    const result = tx_resp.result;

    return result;
  }

  async createOrders(
    walletAddress: string,
    base: any,
    quote: any,
    side: string,
    price: number,
    amount: number
  ): Promise<any> {
    const ripple = Ripple.getInstance(this.network);
    const wallet = await ripple.getWalletFromSeed(walletAddress); // TOFIX: replace with getWallet once decrypting wallet work
    const total = price * amount;
    let we_pay = {
      currency: '',
      issuer: '',
      value: '',
    };
    let we_get = { currency: '', issuer: '', value: '' };

    if (side == 'BUY') {
      we_pay = {
        currency: base.currency,
        issuer: base.issuer,
        value: total.toString(),
      };
      we_get = {
        currency: quote.currency,
        issuer: quote.issuer,
        value: amount.toString(),
      };
    } else {
      we_pay = {
        currency: quote.currency,
        issuer: quote.issuer,
        value: total.toString(),
      };
      we_get = {
        currency: base.currency,
        issuer: base.issuer,
        value: amount.toString(),
      };
    }

    if (we_pay.currency == 'XRP') {
      we_pay.value = xrpToDrops(we_pay.value);
    }

    if (we_get.currency == 'XRP') {
      we_get.value = xrpToDrops(we_get.value);
    }

    const offer: Transaction = {
      TransactionType: 'OfferCreate',
      Account: wallet.classicAddress,
      TakerPays: we_pay,
      TakerGets: we_get.currency == 'XRP' ? we_get.value : we_get,
    };

    await this.client.connect();
    const prepared = await this.client.autofill(offer);
    console.log('Prepared transaction:', JSON.stringify(prepared, null, 2));
    const signed = wallet.sign(prepared);
    console.log('Sending OfferCreate transaction...');
    const response = await this.client.submitAndWait(signed.tx_blob);

    await this.client.disconnect();

    return response;
  }

  async cancelOrders(
    walletAddress: string,
    offerSequence: number
  ): Promise<any> {
    const ripple = Ripple.getInstance(this.network);
    const wallet = await ripple.getWalletFromSeed(walletAddress); // TOFIX: replace with getWallet once decrypting wallet work
    const request: OfferCancel = {
      TransactionType: 'OfferCancel',
      Account: wallet.classicAddress,
      OfferSequence: offerSequence,
    };

    await this.client.connect();
    const prepared = await this.client.autofill(request);
    console.log('Prepared transaction:', JSON.stringify(prepared, null, 2));
    const signed = wallet.sign(prepared);
    console.log('Sending OfferCancel transaction...');
    const response = await this.client.submitAndWait(signed.tx_blob);

    await this.client.disconnect();

    return response;
  }

  async getOpenOrders(address: string): Promise<any> {
    await this.client.connect();

    const account_offers_resp = await this.client.request({
      command: 'account_offers',
      account: address,
    });

    await this.client.disconnect();

    const result = account_offers_resp.result;

    return result;
  }

  ready(): boolean {
    return this._ready;
  }
}
