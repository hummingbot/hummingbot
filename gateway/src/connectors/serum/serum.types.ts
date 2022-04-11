import { PublicKey } from '@solana/web3.js';
import {
  Market as SerumMarket,
  Orderbook as SerumOrderBook,
} from '@project-serum/serum';
import {
  Order as SerumOrder,
  OrderParams as SerumOrderParams,
} from '@project-serum/serum/lib/market';

export interface Market {
  name: string;
  address: PublicKey;
  programId: PublicKey;
  deprecated: boolean;
  market: SerumMarket;
}

export interface OrderBook {
  bids: Order[];
  asks: Order[];
  orderBook: {
    asks: SerumOrderBook;
    bids: SerumOrderBook;
  };
}

export interface Order {
  id: string;
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  order: SerumOrder;
}

export interface Ticker {
  ticker: any;
}

// TODO The OrderSide is using uppercase but the SerumOrderParams use a union type, check!!!
export interface CreateOrder extends SerumOrderParams {
  marketName: string;
  address: string;
}

export interface OrderRequest {
  marketName: string;
  address: string;
  clientOrderId: string;
  exchangeOrderId: string;
}

export interface OrderRequests {
  marketName?: string;
  addresses?: string[];
  clientOrderIds?: string[];
  exchangeOrderIds?: string[];
}

export class SerumishError extends Error {}

export class MarketNotFoundError extends SerumishError {}

export class OrderNotFoundError extends SerumishError {}

// TODO remove comments later!!!
// export interface FeeInfo {
//   maker: string;
//   taker: string;
// }
//
// export interface MarketInfo {
//   name: string;
//   fees: FeeInfo;
//   minimumOrderSize: string; // smallest allowed order size
//   tickSize: string; // smallest possible price increment
//   deprecated: boolean;
// }
//
// export type SimpleOrderBook = {
//   marketName: string;
//   bids: SimpleOrder[];
//   asks: SimpleOrder[];
//   timestamp: string;
// };
//
// /**
//  * Very simple representation of an order.
//  */
// export interface SimpleOrder {
//   price: number;
//   amount: number;
// }
//
// /**
//  * Represents a client's order with IDs and their side.
//  */
// export interface OpenClientOrder extends SimpleOrder {
//   exchangeOrderId: string;
//   clientOrderId?: string;
//   side: 'BUY' | 'SELL';
// }
//
// /**
//  * Represents a filled order.
//  */
// export interface FilledOrder extends OpenClientOrder {
//   id: string; // should be seqNum from FillEvent
//   timestamp: string; // the time at which the fill happened
//   fee: string; // can be positive, when paying, or negative, when rebated
// }
