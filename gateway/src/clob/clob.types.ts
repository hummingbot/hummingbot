export interface Fee {
  maker: string;
  taker: string;
}

export interface Market {
  marketName: string;
  minimumOrderSize: string; // smallest allowed order size
  tickSize: string; // smallest possible price increment
  minimumBaseIncrement?: string;
  fee: Fee; // TODO is this needed?!!!
  deprecated: boolean;
}

export type SimpleOrderBook = {
  marketName: string;
  bids: SimpleOrder[];
  asks: SimpleOrder[];
  timestamp: string;
};

/**
 * Very simple representation of an order.
 */
export interface SimpleOrder {
  price: number;
  amount: number;
}

/**
 * Represents a client's order with IDs and their side.
 */
export interface OpenClientOrder extends SimpleOrder {
  exchangeOrderId: string;
  clientOrderId?: string;
  side: 'BUY' | 'SELL';
}

/**
 * Represents a filled order.
 */
export interface FilledOrder extends OpenClientOrder {
  id: string; // should be seqNum from FillEvent
  timestamp: string; // the time at which the fill happened
  fee: string; // can be positive, when paying, or negative, when rebated
}
