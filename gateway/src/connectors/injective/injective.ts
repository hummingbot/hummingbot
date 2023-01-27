import {
  MsgBatchUpdateOrders,
  IndexerGrpcSpotApi,
  Orderbook,
  SpotOrderHistory,
  GrpcOrderType,
  spotPriceToChainPriceToFixed,
  spotQuantityToChainQuantityToFixed,
} from '@injectivelabs/sdk-ts';
import {
  ClobMarketsRequest,
  ClobOrderbookRequest,
  ClobTickerRequest,
  ClobGetOrderRequest,
  ClobPostOrderRequest,
  ClobDeleteOrderRequest,
  CLOBMarkets,
  ClobGetOrderResponse,
} from '../../clob/clob.requests';
import { NetworkSelectionRequest } from '../../services/common-interfaces';
import { InjectiveCLOBConfig } from './injective.clob.config';
import { Injective } from '../../chains/injective/injective';
import LRUCache from 'lru-cache';
import { getInjectiveConfig } from '../../chains/injective/injective.config';

export class InjectiveCLOB {
  private static _instances: LRUCache<string, InjectiveCLOB>;
  private _chain;
  public conf;
  public spotApi: IndexerGrpcSpotApi;
  private _ready: boolean = false;
  public parsedMarkets: CLOBMarkets = {};

  private constructor(_chain: string, network: string) {
    this._chain = Injective.getInstance(network);
    this.conf = InjectiveCLOBConfig.config;
    this.spotApi = new IndexerGrpcSpotApi(this._chain.endpoints.indexer);
  }

  public static getInstance(chain: string, network: string): InjectiveCLOB {
    if (InjectiveCLOB._instances === undefined) {
      const config = getInjectiveConfig(network);
      InjectiveCLOB._instances = new LRUCache<string, InjectiveCLOB>({
        max: config.network.maxLRUCacheInstances,
      });
    }
    const instanceKey = chain + network;
    if (!InjectiveCLOB._instances.has(instanceKey)) {
      InjectiveCLOB._instances.set(
        instanceKey,
        new InjectiveCLOB(chain, network)
      );
    }

    return InjectiveCLOB._instances.get(instanceKey) as InjectiveCLOB;
  }

  public async loadMarkets() {
    const rawMarkets = await this.spotApi.fetchMarkets();
    for (const market of rawMarkets) {
      this.parsedMarkets[market.ticker.replace('/', '-')] = market;
    }
  }

  public async init() {
    if (!this._chain.ready() || Object.keys(this.parsedMarkets).length === 0) {
      await this._chain.init();
      await this.loadMarkets();
      this._ready = true;
    }
  }

  public ready(): boolean {
    return this._ready;
  }

  public async markets(
    req: ClobMarketsRequest
  ): Promise<{ markets: CLOBMarkets }> {
    if (req.market && req.market.split('-').length === 2) {
      const resp: CLOBMarkets = {};
      resp[req.market] = this.parsedMarkets[req.market];
      return { markets: resp };
    }
    return { markets: this.parsedMarkets };
  }

  public async orderBook(req: ClobOrderbookRequest): Promise<Orderbook> {
    return await this.spotApi.fetchOrderbook(
      this.parsedMarkets[req.market].marketId
    );
  }

  public async ticker(
    req: ClobTickerRequest
  ): Promise<{ markets: CLOBMarkets }> {
    return await this.markets(req);
  }

  public async orders(
    req: ClobGetOrderRequest
  ): Promise<{ orders: ClobGetOrderResponse['orders'] }> {
    if (!req.market) return { orders: [] };
    const marketId = this.parsedMarkets[req.market].marketId;
    const orders: SpotOrderHistory[] = (
      await this.spotApi.fetchOrderHistory({
        subaccountId: req.address,
        marketId,
      })
    ).orderHistory;

    return { orders } as ClobGetOrderResponse;
  }

  public async postOrder(
    req: ClobPostOrderRequest
  ): Promise<{ txHash: string }> {
    const [base, quote] = req.market.split('-');
    const wallet = await this._chain.getWallet(req.address);
    const privateKey: string = wallet.privateKey;
    const injectiveAddress: string = wallet.injectiveAddress;
    const market = this.parsedMarkets[req.market];
    let orderType: GrpcOrderType = req.side === 'BUY' ? 1 : 2;
    orderType =
      req.orderType === 'LIMIT_MAKER'
        ? ((orderType + 6) as GrpcOrderType) // i.e. BUY_LIMIT, SELL_LIMIT are 7, 8 respectively
        : orderType;

    const msg = MsgBatchUpdateOrders.fromJSON({
      subaccountId: req.address,
      injectiveAddress,
      spotOrdersToCreate: [
        {
          orderType,
          price: spotPriceToChainPriceToFixed({
            value: req.price,
            baseDecimals: this._chain.getTokenForSymbol(base)?.decimals,
            quoteDecimals: this._chain.getTokenForSymbol(quote)?.decimals,
          }),
          quantity: spotQuantityToChainQuantityToFixed({
            value: req.amount,
            baseDecimals: this._chain.getTokenForSymbol(base)?.decimals,
          }),
          marketId: market.marketId,
          feeRecipient: injectiveAddress,
        },
      ],
    });

    const { txHash } = await this._chain.broadcaster(privateKey).broadcast({
      msgs: msg,
      injectiveAddress,
    });
    return { txHash };
  }

  public async deleteOrder(
    req: ClobDeleteOrderRequest
  ): Promise<{ txHash: string }> {
    const wallet = await this._chain.getWallet(req.address);
    const privateKey: string = wallet.privateKey;
    const injectiveAddress: string = wallet.injectiveAddress;
    const market = this.parsedMarkets[req.market];

    const msg = MsgBatchUpdateOrders.fromJSON({
      injectiveAddress,
      subaccountId: req.address,
      spotOrdersToCancel: [
        {
          marketId: market.marketId,
          subaccountId: req.address,

          orderHash: req.orderId,
        },
      ],
    });

    const { txHash } = await this._chain.broadcaster(privateKey).broadcast({
      msgs: msg,
      injectiveAddress,
    });
    return { txHash };
  }

  public estimateGas(_req: NetworkSelectionRequest): {
    gasPrice: number;
    gasPriceToken: string;
    gasLimit: number;
    gasCost: number;
  } {
    return {
      gasPrice: this._chain.gasPrice,
      gasPriceToken: this._chain.nativeTokenSymbol,
      gasLimit: this.conf.gasLimitEstimate,
      gasCost: this._chain.gasPrice * this.conf.gasLimitEstimate,
    };
  }
}
