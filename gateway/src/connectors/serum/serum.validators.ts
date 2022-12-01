import { StatusCodes } from 'http-status-codes';
import { HttpException } from '../../services/error-handler';
import {
  isBase58,
  isFloatString,
  isNaturalNumberString,
} from '../../services/validators';
import { OrderSide, OrderType } from './serum.types';

type Validator = <Item>(
  item: undefined | null | any | Item,
  index?: number
) => { warnings: Array<string>; errors: Array<string> };

type RequestValidator = <Item>(item: undefined | null | any | Item) => {
  warnings: Array<string>;
  errors: Array<string>;
};

const createValidator = <Item, Value>(
  accessor: undefined | null | string | ((target: any | Item) => any | Value),
  validation: (
    item: undefined | null | any | Item,
    value: undefined | null | any | Value
  ) => boolean,
  error:
    | string
    | ((
        item: undefined | null | any | Item,
        value: undefined | null | any | Value,
        accessor:
          | undefined
          | null
          | string
          | ((target: any | Item) => any | Value),
        index?: number
      ) => string),
  optional: boolean = false
): Validator => {
  return (item: undefined | null | any | Item, index?: number) => {
    const warnings: Array<string> = [];
    const errors: Array<string> = [];

    let target: any | Value;
    if (item === undefined && accessor) {
      errors.push(`Request with undefined value informed when it shouldn't.`);
    } else if (item === null && accessor) {
      errors.push(`Request with null value informed when it shouldn't.`);
    } else if (!accessor) {
      target = item;
    } else if (typeof accessor === 'string') {
      if (!(`${accessor}` in item) && !optional) {
        errors.push(`The request is missing the key/property "${accessor}".`);
      } else {
        target = item[accessor];
      }
    } else {
      target = accessor(item);
    }

    if (!validation(item, target)) {
      if (typeof error === 'string') {
        if (optional) {
          warnings.push(error);
        } else {
          errors.push(error);
        }
      } else {
        if (optional) {
          warnings.push(error(item, target, accessor, index));
        } else {
          errors.push(error(item, target, accessor, index));
        }
      }
    }

    return {
      warnings,
      errors,
    };
  };
};

export const createRequestValidator = (
  validators: Array<Validator>,
  statusCode?: StatusCodes,
  headerMessage?: (request: any) => string,
  errorNumber?: number
): RequestValidator => {
  return <Item>(request: undefined | null | any | Item) => {
    let warnings: Array<string> = [];
    let errors: Array<string> = [];

    for (const validator of validators) {
      const result = validator(request);
      warnings = [...warnings, ...result.warnings];
      errors = [...errors, ...result.errors];
    }

    throwIfErrorsExist(errors, statusCode, request, headerMessage, errorNumber);

    return { warnings, errors };
  };
};

export const createBatchValidator = <Item>(
  validators: Array<Validator>,
  headerItemMessage?: (
    item: undefined | null | any | Item,
    index?: number
  ) => string
): ((items: any[]) => { warnings: Array<string>; errors: Array<string> }) => {
  return (items: any[]) => {
    let warnings: Array<string> = [];
    let errors: Array<string> = [];

    for (const [index, item] of items.entries()) {
      for (const validator of validators) {
        const itemResult = validator(item, index);

        if (itemResult.warnings && itemResult.warnings.length > 0) {
          if (headerItemMessage) warnings.push(headerItemMessage(item, index));
        }

        if (itemResult.errors && itemResult.errors.length > 0) {
          if (headerItemMessage) errors.push(headerItemMessage(item, index));
        }

        warnings = [...warnings, ...itemResult.warnings];
        errors = [...errors, ...itemResult.errors];
      }
    }

    return { warnings, errors };
  };
};

/**
  Throw an error because the request parameter is malformed, collect all the
    errors related to the request to give the most information possible
 */
export const throwIfErrorsExist = (
  errors: Array<string>,
  statusCode: number = StatusCodes.NOT_FOUND,
  request: any,
  headerMessage?: (request: any, errorNumber?: number) => string,
  errorNumber?: number
): void => {
  if (errors.length > 0) {
    let message = headerMessage
      ? `${headerMessage(request, errorNumber)}\n`
      : '';
    message += errors.join('\n');

    throw new HttpException(statusCode, message);
  }
};

export const validateOrderClientId: Validator = createValidator(
  'id',
  (_, value) => isNaturalNumberString(value),
  (_, value) =>
    `Invalid client id (${value}), it needs to be in big number format.`,
  true
);

export const validateOrderClientIds: Validator = createValidator(
  'ids',
  (_, values) => {
    let ok = true;
    values === undefined
      ? (ok = true)
      : values.map((item: any) => (ok = isNaturalNumberString(item) && ok));
    return ok;
  },
  `Invalid client ids, it needs to be an array of big numbers.`,
  true
);

export const validateOrderExchangeId: Validator = createValidator(
  'exchangeId',
  (_, value) => value === undefined || isNaturalNumberString(value),
  (_, value) =>
    `Invalid exchange id (${value}), it needs to be in big number format.`,
  true
);

export const validateOrderExchangeIds: Validator = createValidator(
  'exchangeIds',
  (_, values) => {
    let ok = true;
    values === undefined
      ? (ok = true)
      : values.map((item: any) => (ok = isNaturalNumberString(item) && ok));
    return ok;
  },
  `Invalid client ids, it needs to be an array of big numbers.`,
  true
);

export const validateOrderMarketName: Validator = createValidator(
  'marketName',
  (_, value) => value.trim().length,
  (_, value) => `Invalid market name (${value}).`,
  false
);

export const validateOrderMarketNames: Validator = createValidator(
  'marketNames',
  (_, values) => {
    let ok = true;
    values === undefined
      ? (ok = true)
      : values.map((item: any) => (ok = item.trim().length && ok));
    return ok;
  },
  `Invalid market names, it needs to be an array of strings.`,
  true
);

export const validateOrderOwnerAddress: Validator = createValidator(
  'ownerAddress',
  (_, value) => isBase58(value),
  (_, value) => `Invalid owner address (${value}).`,
  false
);

export const validateOrderSide: Validator = createValidator(
  'side',
  (_, value) =>
    value &&
    Object.values(OrderSide)
      .map((i) => i.toLowerCase())
      .includes(value.toLowerCase()),
  (_, value) => `Invalid order side (${value}).`,
  false
);

export const validateOrderPrice: Validator = createValidator(
  'price',
  (_, value) => typeof value === 'number' || isFloatString(value),
  (_, value) => `Invalid order price (${value}).`,
  false
);

export const validateOrderAmount: Validator = createValidator(
  'amount',
  (_, value) => typeof value === 'number' || isFloatString(value),
  (_, value) => `Invalid order amount (${value}).`,
  false
);

export const validateOrderType: Validator = createValidator(
  'type',
  (_, value) =>
    value === undefined
      ? true
      : Object.values(OrderType)
          .map((item) => item.toLowerCase())
          .includes(value.toLowerCase()),
  (_, value) => `Invalid order type (${value}).`,
  true
);

export const validateGetMarketRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (request) => request.name,
        `No market was informed. If you want to get a market, please inform the parameter "name".`,
        false
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetMarketsRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (request) => request.names && request.names.length,
        `No markets were informed. If you want to get all markets, please do not inform the parameter "names".`,
        false
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetOrderBookRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (request) => request.marketName,
        `No market name was informed. If you want to get an order book, please inform the parameter "marketName".`,
        false
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetOrderBooksRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (request) => request.marketNames && request.marketNames.length,
        `No market names were informed. If you want to get all order books, please do not inform the parameter "marketNames".`,
        false
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetTickerRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (request) => request.marketName,
        `No market name was informed. If you want to get a ticker, please inform the parameter "marketName".`,
        false
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetTickersRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (request) => request.marketNames && request.marketNames.length,
        `No market names were informed. If you want to get all tickers, please do not inform the parameter "marketNames".`,
        false
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetOrderRequest: RequestValidator = createRequestValidator(
  [
    validateOrderClientId,
    validateOrderExchangeId,
    createValidator(
      null,
      (request) =>
        !(
          request &&
          request.id === undefined &&
          request.exchangeId === undefined
        ),
      `No client id or exchange id were informed.`,
      false
    ),
    // validateOrderMarketName,
    validateOrderOwnerAddress,
  ],
  StatusCodes.BAD_REQUEST,
  (request) => `Error when trying to get order "${request.id}"`
);

export const validateGetOrdersRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (values) => values && values.length,
        `No orders were informed.`,
        false
      ),
      createBatchValidator(
        [
          validateOrderClientId,
          validateOrderExchangeId,
          createValidator(
            null,
            (request) =>
              !(
                request &&
                request.ids === undefined &&
                request.exchangeIds === undefined
              ),
            `No client ids or exchange ids were informed.`,
            false
          ),
          // validateOrderMarketName,
          validateOrderOwnerAddress,
        ],
        (_, index) => `Invalid get orders request at position ${index}:`
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetAllOrdersRequest: RequestValidator =
  createRequestValidator([validateOrderOwnerAddress], StatusCodes.BAD_REQUEST);

export const validateCreateOrderRequest: RequestValidator =
  createRequestValidator(
    [
      validateOrderClientId,
      validateOrderMarketName,
      validateOrderOwnerAddress,
      validateOrderSide,
      validateOrderPrice,
      validateOrderAmount,
      validateOrderType,
    ],
    StatusCodes.BAD_REQUEST,
    (request) => `Error when trying to create order "${request.id}"`
  );

export const validateCreateOrdersRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (values) => values && values.length,
        `No orders were informed.`,
        false
      ),
      createBatchValidator(
        [
          validateOrderClientId,
          validateOrderMarketName,
          validateOrderOwnerAddress,
          validateOrderSide,
          validateOrderPrice,
          validateOrderAmount,
          validateOrderType,
        ],
        (item, index) =>
          `Invalid create orders request at position ${index} with id / exchange id "${item.id} / ${item.exchangeId}":`
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateCancelOrderRequest: RequestValidator =
  createRequestValidator(
    [
      validateOrderClientId,
      validateOrderExchangeId,
      validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    StatusCodes.BAD_REQUEST,
    (request) => `Error when trying to cancel order "${request.id}"`
  );

export const validateCancelOrdersRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (values) => values && values.length,
        `No orders were informed.`,
        false
      ),
      createBatchValidator(
        [
          validateOrderClientIds,
          validateOrderExchangeIds,
          validateOrderMarketName,
          validateOrderOwnerAddress,
        ],
        (_, index) => `Invalid cancel orders request at position ${index}:`
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateCancelAllOrdersRequest: RequestValidator =
  createRequestValidator([validateOrderOwnerAddress], StatusCodes.BAD_REQUEST);

export const validateGetOpenOrderRequest: RequestValidator =
  createRequestValidator(
    [
      validateOrderClientId,
      validateOrderExchangeId,
      createValidator(
        null,
        (request) =>
          !(
            request &&
            request.id === undefined &&
            request.exchangeId === undefined
          ),
        `No client id or exchange id were informed.`,
        false
      ),
      // validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    StatusCodes.BAD_REQUEST,
    (request) => `Error when trying to get open order "${request.id}"`
  );

export const validateGetOpenOrdersRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (values) => values && values.length,
        `No orders were informed.`,
        false
      ),
      createBatchValidator(
        [
          validateOrderClientIds,
          validateOrderExchangeIds,
          createValidator(
            null,
            (request) =>
              !(
                request &&
                request.ids === undefined &&
                request.exchangeIds === undefined
              ),
            `No client ids or exchange ids were informed.`,
            false
          ),
          // validateOrderMarketName,
          validateOrderOwnerAddress,
        ],
        (_, index) => `Invalid get open orders request at position ${index}:`
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateGetFilledOrderRequest: RequestValidator =
  createRequestValidator(
    [
      validateOrderClientId,
      validateOrderExchangeId,
      createValidator(
        null,
        (request) =>
          !(
            request &&
            request.id === undefined &&
            request.exchangeId === undefined
          ),
        `No client id or exchange id were informed.`,
        false
      ),
      // validateOrderMarketName,
      validateOrderOwnerAddress,
    ],
    StatusCodes.BAD_REQUEST,
    (request) => `Error when trying to get filled order "${request.id}"`
  );

export const validateGetFilledOrdersRequest: RequestValidator =
  createRequestValidator(
    [
      createValidator(
        null,
        (values) => values && values.length,
        `No orders were informed.`,
        false
      ),
      createBatchValidator(
        [
          validateOrderClientIds,
          validateOrderExchangeIds,
          createValidator(
            null,
            (request) =>
              !(
                request &&
                request.ids === undefined &&
                request.exchangeIds === undefined
              ),
            `No client ids or exchange ids were informed.`,
            false
          ),
          // validateOrderMarketName,
          validateOrderOwnerAddress,
        ],
        (_, index) => `Invalid get filled orders request at position ${index}:`
      ),
    ],
    StatusCodes.BAD_REQUEST
  );

export const validateSettleFundsRequest: RequestValidator =
  createRequestValidator(
    [validateOrderMarketName, validateOrderOwnerAddress],
    StatusCodes.BAD_REQUEST,
    (request) =>
      `Error when trying to settle funds for market "${request.marketName}."`
  );

export const validateSettleFundsSeveralRequest: RequestValidator =
  createRequestValidator(
    [validateOrderMarketNames, validateOrderOwnerAddress],
    StatusCodes.BAD_REQUEST
  );

export const validateSettleAllFundsRequest: RequestValidator =
  createRequestValidator([validateOrderOwnerAddress], StatusCodes.BAD_REQUEST);
