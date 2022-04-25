import {
  CancelOpenOrderResponse,
  CancelOpenOrdersResponse,
  CancelOrderResponse,
  CancelOrdersResponse,
  CreateOrderResponse,
  CreateOrdersRequest,
  CreateOrdersResponse,
  GetFilledOrderResponse,
  GetFilledOrdersResponse,
  GetMarketResponse,
  GetMarketsResponse,
  GetOpenOrderResponse,
  GetOpenOrdersResponse,
  GetOrderBookResponse,
  GetOrderBooksResponse,
  GetOrderResponse,
  GetOrdersResponse,
  GetTickerResponse,
  GetTickersResponse,
  Market,
  Order,
  OrderBook,
  OrderSide,
  OrderStatus,
  OrderType,
  Ticker
} from "./serum.types";
import {Map as ImmutableMap} from 'immutable';
import {Market as SerumMarket, Order as SerumOrder, OrderParams} from "@project-serum/serum/lib/market";

export enum Types {
  GetMarketsResponse = 'GetMarketsResponse',
  GetTickersResponse = 'GetTickersResponse',
  GetOrderBooksResponse = 'GetOrderBooksResponse',
  GetOrdersResponse = 'GetOrdersResponse',
  GetOpenOrdersResponse = 'GetOpenOrdersResponse',
  GetFilledOrdersResponse = 'GetFilledOrdersResponse',
  CreateOrdersResponse = 'CreateOrdersResponse',
  CancelOrdersResponse = 'CancelOrdersResponse',
  CancelOpenOrdersResponse = 'CancelOpenOrdersResponse',
}

type SingleInput =
  Market
  | OrderBook
  | Ticker
  | Order
;

type InputMap =
  ImmutableMap<string, Market>
  | ImmutableMap<string, OrderBook>
  | ImmutableMap<string, Ticker>
  | ImmutableMap<string, Order>
;

type Input =
  SingleInput
  | InputMap
;

type Output =
  GetMarketsResponse
  | GetOrderBooksResponse
  | GetTickersResponse
  | GetOrdersResponse
  | CreateOrdersResponse
  | CancelOrdersResponse
  | GetOpenOrdersResponse
  | CancelOpenOrdersResponse
  | GetFilledOrdersResponse
  ;

export const convert =
  <
    I extends Input,
    O extends Output
  >(
    input: I,
    type: Types
  ):
O => {
  if (ImmutableMap.isMap(input)) {
    return convertMap<O>(input as InputMap, type);
  }

  return convertSingle<O>(input as SingleInput, type);
}

export const convertMap = <O extends Output>(
  input: InputMap,
  type: Types
): O => {
  const output = ImmutableMap<string, O>().asMutable();

  if (ImmutableMap.isMap(input)) {
    input.forEach((value, key) => {
      output.set(key, convert<Input, O>(value, type));
    });
  }

  return output as unknown as O;
}

export const convertSingle = <O extends Output>(input: SingleInput, type: Types): O => {
  if (type == Types.GetMarketsResponse)
    return convertToGetMarketResponse(input as Market) as O;

  if (type as Types.GetOrderBooksResponse)
    return convertToGetOrderBookResponse(input as OrderBook) as O;

  if (type as Types.GetTickersResponse)
    return convertToGetTickerResponse(input as Ticker) as O;

  if (type as Types.GetOrdersResponse)
    return convertToGetOrderResponse(input as Order) as O;

  if (type as Types.CreateOrdersResponse)
    return convertToCreateOrderResponse(input as Order) as O;

  if (type as Types.CancelOrdersResponse)
    return convertToCancelOrderResponse(input as Order) as O;

  if (type as Types.GetOpenOrdersResponse)
    return convertToGetOpenOrderResponse(input as Order) as O;

  if (type as Types.CancelOpenOrdersResponse)
    return convertToCancelOpenOrderResponse(input as Order) as O;

  if (type as Types.GetFilledOrdersResponse)
    return convertToGetFilledOrderResponse(input as Order) as O;

  throw new Error(`Unsupported input type "${type}".`);
};

export const convertSerumMarketToMarket = (
  market: SerumMarket,
  extraInfo: Record<string, unknown>,
): Market => {
  return {
    name: extraInfo.name,
    address: extraInfo.address,
    programId: extraInfo.programId,
    deprecated: extraInfo.deprecated,
    minimumOrderSize: market.minOrderSize,
    tickSize: market.tickSize,
    minimumBaseIncrement: market.baseSizeLotsToNumber(market.decoded.baseLotSize), // TODO is this correct?!!!
    fees: market.decoded.fee,
    market: market
  } as Market;
}

export const convertFilledOrderToTicker = (timestamp: number, fill: any): Ticker => {
  return {
    price: fill.price,
    amount: fill.size,
    side: convertSerumSideToOrderSide(fill.side),
    timestamp: timestamp,
    ticker: fill
  };
}

export const convertSerumOrderToOrder = (
  market: Market,
  order?: SerumOrder, // | Record<string, unknown>,
  candidate?: CreateOrdersRequest,
  orderParameters?: OrderParams,
  status?: OrderStatus,
  signature?: string,
): Order => {
  // TODO Add clientId and exchangeId!!!
  // TODO convert the loadFills and placeOrder returns too!!!
  // TODO return the clientOrderId and status pending when creating a new order (the exchangeOrderId will not be sent)!!!

  return {
    id: order?.clientId?.toString() || candidate?.id || undefined,
    exchangeId: order?.orderId.toString() || undefined,
    marketName: market.name,
    ownerAddress: order?.openOrdersAddress.toString() || candidate!.ownerAddress,
    price: order?.price || candidate!.price,
    amount: order?.size || candidate!.amount,
    side: order ? convertSerumSideToOrderSide(order?.side) : candidate!.side,
    status: status,
    type: orderParameters ? convertSerumTypeToOrderType(orderParameters.orderType!): undefined,
    fee: order?.feeTier || undefined, //TODO order.feeTier?!!!
    fillmentTimestamp: undefined,
    signature: signature,
    order: order
  };
};

export const convertToGetMarketResponse = (input: Market): GetMarketResponse => {
  return {
    name: input.name,
    address: input.address,
    programId: input.programId,
    deprecated: input.deprecated,
    minimumOrderSize: input.minimumOrderSize,
    tickSize: input.tickSize,
    minimumBaseIncrement: input.minimumBaseIncrement,
    fees: input.fees
  }
}

export const convertToGetOrderBookResponse = (input: OrderBook): GetOrderBookResponse => {
  return {
    market: convertToGetMarketResponse(input.market),
    bids: input.bids.map(item => convertToGetOrderResponse(item)),
    asks: input.asks.map(item => convertToGetOrderResponse(item))
  }
}

export const convertToGetTickerResponse = (input: Ticker): GetTickerResponse => {
  return {
    price: input.price,
    amount: input.amount,
    side: input.side,
    timestamp: input.timestamp
  }
}

export const convertToGetOrderResponse = (input: Order): GetOrderResponse => {
  return {
    id: input.id,
    exchangeId: input.exchangeId,
    marketName: input.marketName,
    ownerAddress: input.ownerAddress,
    price: input.price,
    amount: input.amount,
    side: input.side,
    status: input.status,
    type: input.type,
    fee: input.fee,
    fillmentTimestamp: input.fillmentTimestamp,
  }
}

export const convertToCreateOrderResponse = (input: Order): CreateOrderResponse => {
  return {
    id: input.id,
    exchangeId: input.exchangeId,
    marketName: input.marketName,
    ownerAddress: input.ownerAddress,
    price: input.price,
    amount: input.amount,
    side: input.side,
    status: input.status,
    type: input.type,
    fee: input.fee
  }
}

export const convertToCancelOrderResponse = (input: Order): CancelOrderResponse => {
  return {
    id: input.id,
    exchangeId: input.exchangeId,
    marketName: input.marketName,
    ownerAddress: input.ownerAddress,
    price: input.price,
    amount: input.amount,
    side: input.side,
    status: input.status,
    type: input.type,
    fee: input.fee
  }
}

export const convertToGetOpenOrderResponse = (input: Order): GetOpenOrderResponse => {
  return {
    id: input.id,
    exchangeId: input.exchangeId,
    marketName: input.marketName,
    ownerAddress: input.ownerAddress,
    price: input.price,
    amount: input.amount,
    side: input.side,
    status: input.status,
    type: input.type,
    fee: input.fee
  }
}

export const convertToCancelOpenOrderResponse = (input: Order): CancelOpenOrderResponse => ({
  id: input.id,
  exchangeId: input.exchangeId,
  marketName: input.marketName,
  ownerAddress: input.ownerAddress,
  price: input.price,
  amount: input.amount,
  side: input.side,
  status: input.status,
  type: input.type,
  fee: input.fee
})

export const convertToGetFilledOrderResponse = (input: Order): GetFilledOrderResponse => {
  return {
    id: input.id,
    exchangeId: input.exchangeId,
    marketName: input.marketName,
    ownerAddress: input.ownerAddress,
    price: input.price,
    amount: input.amount,
    side: input.side,
    status: input.status,
    type: input.type,
    fee: input.fee,
    fillmentTimestamp: input.fillmentTimestamp
  }
}

export const convertOrderSideToSerumSide = (input: OrderSide): 'buy' | 'sell' => {
  return input.toLowerCase() as 'buy' | 'sell'
}

export const convertSerumSideToOrderSide = (input: 'buy' | 'sell'): OrderSide => {
  if (input == 'buy') return OrderSide.BUY;
  if (input == 'sell') return OrderSide.SELL;
  throw new Error(`Invalid order side: ${input}`);
}

export const convertOrderTypeToSerumType = (input?: OrderType): 'limit' | 'ioc' | 'postOnly' => {
  if (!input)
    return 'limit'
  else if (['limit', 'ioc'].includes(input.toLowerCase()))
    return input.toLowerCase() as 'limit' | 'ioc' | 'postOnly'
  else if (['post_only', 'postOnly'].includes(input.toLowerCase()))
    return 'postOnly'
  else
    throw new Error(`Invalid order type: ${input}`)
}

export const convertSerumTypeToOrderType = (input: 'limit' | 'ioc' | 'postOnly'): OrderType => {
  if (input == 'limit') return OrderType.LIMIT;
  if (input == 'ioc') return OrderType.IOC;
  if (input == 'postOnly') return OrderType.POST_ONLY;
  throw new Error(`Invalid order type: ${input}`);
}
