import { StatusCodes } from 'http-status-codes';
import {
  isBase58,
  isFloatString,
  isNaturalNumberString,
  mkBatchValidator,
  mkRequestValidator,
  mkValidator,
  RequestValidator,
  Validator,
} from '../../services/validators';
import { OrderSide, OrderType } from './serum.types';

export const validateOrderClientId: Validator = mkValidator(
  'id',
  (value) => `Invalid client id (${value}), it needs to be in big number format.`,
  (target) => isNaturalNumberString(target),
  true
);

export const validateOrderClientIds: Validator = mkValidator(
  'ids',
  (_value) => `Invalid client ids, it needs to be an array of big numbers.`,
  (target) => {
    let ok = true;
    target === undefined ? ok = true : target.map((item: any) => ok = isNaturalNumberString(item) && ok);
    return ok;
  },
  true
);

export const validateOrderExchangeId: Validator = mkValidator(
  'exchangeId',
  (value) => `Invalid exchange id (${value}), it needs to be in big number format.`,
  (target) => target === undefined || isNaturalNumberString(target),
  true
);

export const validateOrderExchangeIds: Validator = mkValidator(
  'exchangeIds',
  (_value) => `Invalid client ids, it needs to be an array of big numbers.`,
  (target) => {
    let ok = true;
    target === undefined ? ok = true : target.map((item: any) => ok = isNaturalNumberString(item) && ok);
    return ok;
  },
  true
);

export const validateOrderMarketName: Validator = mkValidator(
  'marketName',
  (value) => `Invalid market name (${value}).`,
  (target) => target.trim().length,
  false
);

export const validateOrderMarketNames: Validator = mkValidator(
  'marketNames',
  (_value) => `Invalid market names, it needs to be an array of strings.`,
  (target) => {
    let ok = true;
    target === undefined ? ok = true : target.map((item: any) => ok = item.trim().length && ok);
    return ok;
  },
  true
);

export const validateOrderOwnerAddress: Validator = mkValidator(
  'ownerAddress',
  (value) => `Invalid owner address (${value}).`,
  (target) => isBase58(target),
  false
);

export const validateOrderSide: Validator = mkValidator(
  'side',
  (value) => `Invalid order side (${value}).`,
  (target) => Object.values(OrderSide).map(i => i.toLowerCase()).includes(target.toLowerCase()),
  false
);

export const validateOrderPrice: Validator = mkValidator(
  'price',
  (value) => `Invalid order price (${value}).`,
  (target) => typeof target === 'number' || isFloatString(target),
  false
);

export const validateOrderAmount: Validator = mkValidator(
  'amount',
  (value) => `Invalid order amount (${value}).`,
  (target) => typeof target === 'number' || isFloatString(target),
  false
);

export const validateOrderType: Validator = mkValidator(
  'type',
  (value) => `Invalid order type (${value}).`,
  (target) => target === undefined ? true : Object.values(OrderType).map(item => item.toLowerCase()).includes(target.toLowerCase()),
  true
);

export const validateGetMarketRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No market was informed. If you want to get a market, please inform the parameter "name".`,
    (request) => request.name,
    false,
    true
  )
], StatusCodes.BAD_REQUEST);

export const validateGetMarketsRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No markets were informed. If you want to get all markets, please do not inform the parameter "names".`,
    (request) => request.names && request.names.length,
    false,
    true
  )
], StatusCodes.BAD_REQUEST);

export const validateGetOrderBookRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No market name was informed. If you want to get an order book, please inform the parameter "marketName".`,
    (request) => request.marketName,
    false,
    true
  )
], StatusCodes.BAD_REQUEST);

export const validateGetOrderBooksRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No market names were informed. If you want to get all order books, please do not inform the parameter "marketNames".`,
    (request) => request.marketNames && request.marketNames.length,
    false,
    true
  )
], StatusCodes.BAD_REQUEST);

export const validateGetTickerRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No market name was informed. If you want to get a ticker, please inform the parameter "marketName".`,
    (request) => request.marketName,
    false,
    true
  )
], StatusCodes.BAD_REQUEST);

export const validateGetTickersRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No market names were informed. If you want to get all tickers, please do not inform the parameter "marketNames".`,
    (request) => request.marketNames && request.marketNames.length,
    false,
    true
  )
], StatusCodes.BAD_REQUEST);

export const validateGetOrderRequest: RequestValidator = mkRequestValidator(
  [
    validateOrderClientId,
    validateOrderExchangeId,
    // validateOrderMarketName,
    validateOrderOwnerAddress,
  ], StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to get order "${request.id}"`
);

export const validateGetOrdersRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No orders were informed.`,
    (request) => request && request.length,
    false,
    true
  ),
  mkBatchValidator(
    [
      validateOrderClientIds,
      validateOrderExchangeIds,
      // validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    (_item, index) => `Invalid get orders request at position ${index}:`
  )
], StatusCodes.BAD_REQUEST);

export const validateCreateOrderRequest: RequestValidator = mkRequestValidator(
  [
    validateOrderClientId,
    validateOrderMarketName,
    validateOrderOwnerAddress,
    validateOrderSide,
    validateOrderPrice,
    validateOrderAmount,
    validateOrderType
  ], StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to create order "${request.id}"`
);

export const validateCreateOrdersRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No orders were informed.`,
    (request) => request && request.length,
    false,
    true
  ),
  mkBatchValidator(
    [
      validateOrderClientId,
      validateOrderMarketName,
      validateOrderOwnerAddress,
      validateOrderSide,
      validateOrderPrice,
      validateOrderAmount,
      validateOrderType
    ],
    (item, index) => `Invalid create orders request at position ${index} with id / exchange id "${item.id} / ${item.exchangeId}":`
  )
], StatusCodes.BAD_REQUEST);

export const validateCancelOrderRequest: RequestValidator = mkRequestValidator(
  [
    validateOrderClientId,
    validateOrderExchangeId,
    validateOrderMarketName,
    validateOrderOwnerAddress,
  ], StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to cancel order "${request.id}"`
);

export const validateCancelOrdersRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No orders were informed.`,
    (request) => request && request.length,
    false,
    true
  ),
  mkBatchValidator(
    [
      validateOrderClientIds,
      validateOrderExchangeIds,
      validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    (_item, index) => `Invalid cancel orders request at position ${index}:`
  )
], StatusCodes.BAD_REQUEST);

export const validateGetOpenOrderRequest: RequestValidator = mkRequestValidator(
  [
    validateOrderClientId,
    validateOrderExchangeId,
    // validateOrderMarketName,
    validateOrderOwnerAddress,
  ], StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to get open order "${request.id}"`
);

export const validateGetOpenOrdersRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No orders were informed.`,
    (request) => request && request.length,
    false,
    true
  ),
  mkBatchValidator(
    [
      validateOrderClientIds,
      validateOrderExchangeIds,
      // validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    (_item, index) => `Invalid get open orders request at position ${index}:`
  )
], StatusCodes.BAD_REQUEST);

export const validateCancelOpenOrderRequest: RequestValidator = mkRequestValidator(
  [
    validateOrderClientId,
    validateOrderExchangeId,
    validateOrderMarketName,
    validateOrderOwnerAddress,
  ], StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to cancel open order "${request.id}"`
);

export const validateCancelOpenOrdersRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No orders were informed.`,
    (request) => request && request.length,
    false,
    true
  ),
  mkBatchValidator(
    [
      validateOrderClientIds,
      validateOrderExchangeIds,
      validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    (_item, index) => `Invalid cancel open orders request at position ${index}:`
  )
], StatusCodes.BAD_REQUEST);

export const validateGetFilledOrderRequest: RequestValidator = mkRequestValidator(
  [
    validateOrderClientId,
    validateOrderExchangeId,
    // validateOrderMarketName,
    validateOrderOwnerAddress,
  ], StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to get filled order "${request.id}"`
);

export const validateGetFilledOrdersRequest: RequestValidator = mkRequestValidator([
  mkValidator(
    '',
    (_request) => `No orders were informed.`,
    (request) => request && request.length,
    false,
    true
  ),
  mkBatchValidator(
    [
      validateOrderClientIds,
      validateOrderExchangeIds,
      // validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    (_item, index) => `Invalid get filled orders request at position ${index}:`
  )
], StatusCodes.BAD_REQUEST);

export const validateSettleFundsRequest: RequestValidator = mkRequestValidator(
  [
    validateOrderMarketName,
    validateOrderOwnerAddress,
  ], StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to settle funds for market "${request.marketName}."`
);

export const validateSettleFundsSeveralRequest: RequestValidator = mkRequestValidator([
  validateOrderMarketNames,
  validateOrderOwnerAddress,
], StatusCodes.BAD_REQUEST);
