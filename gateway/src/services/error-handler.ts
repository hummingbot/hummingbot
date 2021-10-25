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
export const UNKNOWN_ERROR_ERROR_CODE = 1099;

export const NETWORK_ERROR_MESSAGE =
  'Network error. Please check your node URL, API key, and Internet connection.';
export const RATE_LIMIT_ERROR_MESSAGE =
  'Blockchain node API rate limit exceeded.';
export const OUT_OF_GAS_ERROR_MESSAGE = 'Transaction out of gas.';
export const UNKNOWN_ERROR_MESSAGE = 'Unknown error.';
