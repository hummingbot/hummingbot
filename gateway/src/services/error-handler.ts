import { Request, RequestHandler, Response, NextFunction } from 'express';

// error origination from ethers library when interracting with node
export interface NodeError extends Error {
  code: string | number;
  reason?: string;
  data?: any;
}

// custom error for http exceptions
export class HttpException extends Error {
  status: number;
  message: string;
  errorCode: number;
  constructor(status: number, message: string, errorCode: number = -1) {
    super(message);
    this.status = status;
    this.message = message;
    this.errorCode = errorCode;
  }
}

export class InitializationError extends Error {
  message: string;
  errorCode: number;
  constructor(message: string, errorCode: number) {
    super(message);
    this.message = message;
    this.errorCode = errorCode;
  }
}

export class UniswapishPriceError extends Error {
  message: string;
  constructor(message: string) {
    super(message);
    this.message = message;
  }
}

export class InvalidNonceError extends Error {
  message: string;
  errorCode: number;
  constructor(message: string, errorCode: number) {
    super(message);
    this.message = message;
    this.errorCode = errorCode;
  }
}

// Capture errors from an async route, this must wrap any route that uses async.
// For example, `app.get('/', asyncHandler(async (req, res) -> {...}))`
export const asyncHandler =
  (fn: RequestHandler) => (req: Request, res: Response, next: NextFunction) => {
    return Promise.resolve(fn(req, res, next)).catch(next);
  };

export interface TransactionError {
  errorCode: number;
  message: string;
}

export const parseTransactionGasError = (
  error: any
): TransactionError | null => {
  if ('code' in error && error.code === 'SERVER_ERROR') {
    if ('body' in error) {
      const innerError = JSON.parse(error['body']);

      if (
        'error' in innerError &&
        'code' in innerError['error'] &&
        innerError['error']['code'] === -32010 &&
        'message' in innerError['error']
      ) {
        const transactionError: TransactionError = {
          errorCode: TRANSACTION_GAS_PRICE_TOO_LOW,
          message: innerError['error']['message'],
        };

        return transactionError;
      }
    }
  }
  return null;
};

export const NETWORK_ERROR_CODE = 1001;
export const RATE_LIMIT_ERROR_CODE = 1002;
export const OUT_OF_GAS_ERROR_CODE = 1003;
export const TRANSACTION_GAS_PRICE_TOO_LOW = 1004;
export const LOAD_WALLET_ERROR_CODE = 1005;
export const TOKEN_NOT_SUPPORTED_ERROR_CODE = 1006;
export const TRADE_FAILED_ERROR_CODE = 1007;
export const SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE = 1008;
export const SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE = 1009;
export const SERVICE_UNITIALIZED_ERROR_CODE = 1010;
export const UNKNOWN_CHAIN_ERROR_CODE = 1011;
export const INVALID_NONCE_ERROR_CODE = 1012;
export const PRICE_FAILED_ERROR_CODE = 1013;
export const INCOMPLETE_REQUEST_PARAM_CODE = 1014;
export const ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_CODE = 1015;
export const ACCOUNT_NOT_SPECIFIED_CODE = 1016;
export const UNKNOWN_ERROR_ERROR_CODE = 1099;

export const NETWORK_ERROR_MESSAGE =
  'Network error. Please check your node URL, API key, and Internet connection.';
export const RATE_LIMIT_ERROR_MESSAGE =
  'Blockchain node API rate limit exceeded.';
export const OUT_OF_GAS_ERROR_MESSAGE = 'Transaction out of gas.';
export const LOAD_WALLET_ERROR_MESSAGE = 'Failed to load wallet: ';
export const TOKEN_NOT_SUPPORTED_ERROR_MESSAGE = 'Token not supported: ';
export const TRADE_FAILED_ERROR_MESSAGE = 'Trade query failed: ';
export const INCOMPLETE_REQUEST_PARAM = 'Incomplete request parameters.';
export const INVALID_NONCE_ERROR_MESSAGE = 'Invalid Nonce provided: ';
export const SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE = (
  price: any,
  limitPrice: any
) => `Swap price ${price} exceeds limitPrice ${limitPrice}`;

export const SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE = (
  price: any,
  limitPrice: any
) => `Swap price ${price} lower than limitPrice ${limitPrice}`;

export const SERVICE_UNITIALIZED_ERROR_MESSAGE = (service: any) =>
  `${service} was called before being initialized.`;

export const UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE = (chainName: any) =>
  `Unrecognized chain name ${chainName}.`;

export const ACCOUNT_NOT_SPECIFIED_ERROR_MESSAGE = () =>
  `AccountID or address not specified.`;

export const ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_MESSAGE = (
  privKey: string
) =>
  `Unable to retrieve wallet address for provided private key: ${privKey.substring(
    0,
    5
  )}`;

export const UNKNOWN_ERROR_MESSAGE = 'Unknown error.';

export const PRICE_FAILED_ERROR_MESSAGE = 'Price query failed: ';

export interface ErrorResponse {
  stack?: any;
  message: string;
  httpErrorCode: number;
  errorCode: number;
}

export const gatewayErrorMiddleware = (
  err: Error | NodeError | HttpException | InitializationError
): ErrorResponse => {
  const response: ErrorResponse = {
    message: err.message || UNKNOWN_ERROR_MESSAGE,
    httpErrorCode: 503,
    errorCode: UNKNOWN_ERROR_ERROR_CODE,
    stack: err.stack,
  };
  // the default http error code is 503 for an unknown error
  if (err instanceof HttpException) {
    response.httpErrorCode = err.status;
    response.errorCode = err.errorCode;
  } else if (err instanceof InitializationError) {
    response.errorCode = err.errorCode;
  } else {
    response.errorCode = UNKNOWN_ERROR_ERROR_CODE;
    response.message = UNKNOWN_ERROR_MESSAGE;

    if ('code' in err) {
      switch (typeof err.code) {
        case 'string':
          // error is from ethers library
          if (['NETWORK_ERROR', 'TIMEOUT'].includes(err.code)) {
            response.errorCode = NETWORK_ERROR_CODE;
            response.message = NETWORK_ERROR_MESSAGE;
          } else if (err.code === 'SERVER_ERROR') {
            const transactionError = parseTransactionGasError(err);
            if (transactionError) {
              response.errorCode = transactionError.errorCode;
              response.message = transactionError.message;
            } else {
              response.errorCode = NETWORK_ERROR_CODE;
              response.message = NETWORK_ERROR_MESSAGE;
            }
          }
          break;

        case 'number':
          // errors from provider, this code comes from infura
          if (err.code === -32005) {
            // we only handle rate-limit errors
            response.errorCode = RATE_LIMIT_ERROR_CODE;
            response.message = RATE_LIMIT_ERROR_MESSAGE;
          } else if (err.code === -32010) {
            response.errorCode = TRANSACTION_GAS_PRICE_TOO_LOW;
            response.message = err.message;
          }
          break;
      }
    }
  }
  return response;
};
