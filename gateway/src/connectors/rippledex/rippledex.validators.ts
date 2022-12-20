import { StatusCodes } from 'http-status-codes';
import { HttpException } from '../../services/error-handler';
// import {
//   isBase58,
//   isFloatString,
//   isNaturalNumberString,
// } from '../../services/validators';

type Validator = <Item>(
  item: undefined | null | any | Item,
  index?: number
) => { warnings: Array<string>; errors: Array<string> };

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

type RequestValidator = <Item>(item: undefined | null | any | Item) => {
  warnings: Array<string>;
  errors: Array<string>;
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
