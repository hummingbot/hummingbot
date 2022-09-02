import { getNotNullOrThrowError } from './serum.helpers';
import {
  BasicSerumMarket,
  CancelOrderResponse,
  CancelOrdersResponse,
  CreateOrderResponse,
  CreateOrdersRequest,
  CreateOrdersResponse,
  Fund,
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
  IMap,
  Market,
  Order,
  OrderBook,
  OrderSide,
  OrderStatus,
  OrderType,
  SettleFundsResponse,
  SerumMarket,
  SerumOrder,
  SerumOrderBook,
  SerumOrderParams,
  Ticker,
} from './serum.types';

export enum Types {
  GetMarketsResponse = 'GetMarketsResponse',
  GetTickersResponse = 'GetTickersResponse',
  GetOrderBooksResponse = 'GetOrderBooksResponse',
  GetOrdersResponse = 'GetOrdersResponse',
  GetOpenOrdersResponse = 'GetOpenOrdersResponse',
  GetFilledOrdersResponse = 'GetFilledOrdersResponse',
  CreateOrdersResponse = 'CreateOrdersResponse',
  CancelOrdersResponse = 'CancelOrdersResponse',
  PostSettleFundsResponse = 'PostSettleFundsResponse',
}

type SingleInput = Market | OrderBook | Ticker | Order | Fund[];

type InputMap =
  | IMap<string, Market>
  | IMap<string, OrderBook>
  | IMap<string, Ticker>
  | IMap<string, Order>
  | IMap<string, Fund[]>;

type InputMapMap = IMap<string, InputMap>;

type Input = SingleInput | InputMap | InputMapMap;

type SingleOutput =
  | GetMarketsResponse
  | GetOrderBooksResponse
  | GetTickersResponse
  | GetOrdersResponse
  | CreateOrdersResponse
  | CancelOrdersResponse
  | GetOpenOrdersResponse
  | GetFilledOrdersResponse
  | SettleFundsResponse;

type Output = SingleOutput;

export const convert = <I extends Input, O extends Output>(
  input: I,
  type: Types
): O => {
  if (IMap.isMap(input)) {
    if (IMap.isMap(input.first())) {
      return convertMapMap(input as InputMapMap, type);
    }

    return convertMap(input as InputMap, type);
  }

  return convertSingle<O>(input as SingleInput, type);
};

export const convertMapMap = <O extends Output>(
  input: InputMapMap,
  type: Types
): O => {
  const output = IMap<string, O>().asMutable();

  if (IMap.isMap(input)) {
    if (IMap.isMap(input.first())) {
      input.forEach((value: InputMap, key: string) => {
        output.set(key, convert<InputMap, O>(value, type));
      });
    }
  }

  return output as unknown as O;
};

export const convertMap = <O extends Output>(
  input: InputMap,
  type: Types
): O => {
  const output = IMap<string, O>().asMutable();

  if (IMap.isMap(input)) {
    input.forEach((value: SingleInput, key: string) => {
      output.set(key, convert<Input, O>(value, type));
    });
  }

  return output as unknown as O;
};

export const convertSingle = <O extends Output>(
  input: SingleInput,
  type: Types
): O => {
  if (type === Types.GetMarketsResponse)
    return convertToGetMarketResponse(input as Market) as O;

  if (type === Types.GetOrderBooksResponse)
    return convertToGetOrderBookResponse(input as OrderBook) as O;

  if (type === Types.GetTickersResponse)
    return convertToGetTickerResponse(input as Ticker) as O;

  if (type === Types.GetOrdersResponse)
    return convertToGetOrderResponse(input as Order) as O;

  if (type === Types.CreateOrdersResponse)
    return convertToCreateOrderResponse(input as Order) as O;

  if (type === Types.CancelOrdersResponse)
    return convertToCancelOrderResponse(input as Order) as O;

  if (type === Types.GetOpenOrdersResponse)
    return convertToGetOpenOrderResponse(input as Order) as O;

  if (type === Types.GetFilledOrdersResponse)
    return convertToGetFilledOrderResponse(input as Order) as O;

  if (type === Types.PostSettleFundsResponse)
    return convertToPostSettleFundsResponse(input as Fund[]) as O;

  throw new Error(`Unsupported input type "${type}".`);
};

export const convertToJsonIfNeeded = (input: any): any => {
  let output = input;

  if (IMap.isMap(input)) output = input.toJS();

  return output;
};

export const convertSerumMarketToMarket = (
  market: SerumMarket,
  extraInfo: Record<string, unknown> | BasicSerumMarket
): Market => {
  return {
    name: extraInfo.name,
    address: extraInfo.address,
    programId: extraInfo.programId,
    deprecated: extraInfo.deprecated,
    minimumOrderSize: market.minOrderSize,
    tickSize: market.tickSize,
    minimumBaseIncrement: market.decoded.baseLotSize,
    fees: market.decoded.fee,
    market: market,
  } as Market;
};

export const convertMarketBidsAndAsksToOrderBook = (
  market: Market,
  asks: SerumOrderBook,
  bids: SerumOrderBook
): OrderBook => {
  return {
    market: market,
    asks: convertArrayOfSerumOrdersToMapOfOrders(market, asks, undefined),
    bids: convertArrayOfSerumOrdersToMapOfOrders(market, bids, undefined),
    orderBook: {
      asks: asks,
      bids: bids,
    },
  } as OrderBook;
};

export const convertArrayOfSerumOrdersToMapOfOrders = (
  market: Market,
  orders: SerumOrder[] | SerumOrderBook | any[],
  ownerAddress?: string,
  status?: OrderStatus
): IMap<string, Order> => {
  const result = IMap<string, Order>().asMutable();

  for (const order of orders) {
    result.set(
      order.clientId || order.orderId,
      convertSerumOrderToOrder(
        market,
        order,
        undefined,
        undefined,
        ownerAddress,
        status
      )
    );
  }

  return result;
};

export const convertToTicker = (input: any): Ticker => {
  const price = parseFloat(input.price);
  const timestamp = new Date(input.last_updated).getTime();

  return {
    price: price,
    timestamp: timestamp,
    ticker: input,
  };
};

export const convertSerumOrderToOrder = (
  market: Market,
  order?: SerumOrder, // | Record<string, unknown>,
  candidate?: CreateOrdersRequest,
  orderParameters?: SerumOrderParams<any>,
  ownerAddress?: string,
  status?: OrderStatus,
  signature?: string
): Order => {
  return {
    id: order?.clientId?.toString() || candidate?.id || undefined,
    exchangeId: order?.orderId.toString() || undefined, // TODO check the possibility to retrieve the exchange id from a new order.
    marketName: market.name,
    ownerAddress: ownerAddress || candidate?.ownerAddress,
    price: getNotNullOrThrowError(
      order?.price || candidate?.price,
      'Price is not defined.'
    ),
    amount: getNotNullOrThrowError(
      order?.size || candidate?.amount,
      'Amount is not defined.'
    ),
    side: getNotNullOrThrowError(
      order ? convertSerumSideToOrderSide(order.side) : candidate?.side,
      'Side is not defined.'
    ),
    status: status,
    type:
      orderParameters && orderParameters.orderType
        ? convertSerumTypeToOrderType(orderParameters.orderType)
        : undefined,
    fillmentTimestamp: undefined,
    signature: signature,
    order: order,
  };
};

export const convertToGetMarketResponse = (
  input: Market
): GetMarketResponse => {
  return {
    name: input.name,
    address: input.address,
    programId: input.programId,
    deprecated: input.deprecated,
    minimumOrderSize: input.minimumOrderSize,
    tickSize: input.tickSize,
    minimumBaseIncrement: input.minimumBaseIncrement?.toString(),
    fees: input.fees,
  };
};

export const convertToGetOrderBookResponse = (
  input: OrderBook
): GetOrderBookResponse => {
  return {
    market: convertToGetMarketResponse(input.market),
    bids: input.bids
      .map((item) => convertToGetOrderResponse(item))
      .toJS() as unknown as Map<string, any>,
    asks: input.asks
      .map((item) => convertToGetOrderResponse(item))
      .toJS() as unknown as Map<string, any>,
  };
};

export const convertToGetTickerResponse = (
  input: Ticker
): GetTickerResponse => {
  return {
    price: input.price,
    timestamp: input.timestamp,
  };
};

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
    fillmentTimestamp: input.fillmentTimestamp,
  };
};

export const convertToCreateOrderResponse = (
  input: Order
): CreateOrderResponse => {
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
    signature: input.signature,
  };
};

export const convertToCancelOrderResponse = (
  input: Order
): CancelOrderResponse => {
  return {
    id: input.id,
    exchangeId: input.exchangeId,
    marketName: input.marketName,
    ownerAddress: getNotNullOrThrowError(
      input.ownerAddress,
      'Owner address is not defined.'
    ),
    price: input.price,
    amount: input.amount,
    side: input.side,
    status: input.status,
    type: input.type,
    signature: input.signature,
  };
};

export const convertToGetOpenOrderResponse = (
  input: Order
): GetOpenOrderResponse => {
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
  };
};

export const convertToGetFilledOrderResponse = (
  input: Order
): GetFilledOrderResponse => {
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
    fillmentTimestamp: input.fillmentTimestamp,
  };
};

export const convertToPostSettleFundsResponse = (
  input: Fund[]
): SettleFundsResponse => {
  return input;
};

export const convertOrderSideToSerumSide = (
  input: OrderSide
): 'buy' | 'sell' => {
  return input.toLowerCase() as 'buy' | 'sell';
};

export const convertSerumSideToOrderSide = (
  input: 'buy' | 'sell'
): OrderSide => {
  if (input == 'buy') return OrderSide.BUY;
  if (input == 'sell') return OrderSide.SELL;
  throw new Error(`Invalid order side: ${input}`);
};

export const convertOrderTypeToSerumType = (
  input?: OrderType
): 'limit' | 'ioc' | 'postOnly' => {
  if (!input) return 'limit';
  else if (['limit', 'ioc'].includes(input.toLowerCase()))
    return input.toLowerCase() as 'limit' | 'ioc' | 'postOnly';
  else if (['post_only', 'postOnly'].includes(input.toLowerCase()))
    return 'postOnly';
  else throw new Error(`Invalid order type: ${input}`);
};

export const convertSerumTypeToOrderType = (
  input: 'limit' | 'ioc' | 'postOnly'
): OrderType => {
  if (input == 'limit') return OrderType.LIMIT;
  if (input == 'ioc') return OrderType.IOC;
  if (input == 'postOnly') return OrderType.POST_ONLY;
  throw new Error(`Invalid order type: ${input}`);
};
