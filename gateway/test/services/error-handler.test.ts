import {
  parseTransactionGasError,
  TRANSACTION_GAS_PRICE_TOO_LOW,
  UNKNOWN_ERROR_MESSAGE,
  UNKNOWN_ERROR_ERROR_CODE,
  NETWORK_ERROR_CODE,
  NETWORK_ERROR_MESSAGE,
  RATE_LIMIT_ERROR_MESSAGE,
  RATE_LIMIT_ERROR_CODE,
  HttpException,
  gatewayErrorMiddleware,
} from '../../src/services/error-handler';
import 'jest-extended';

describe('parseTransactionGasError', () => {
  test('return null for a normal Error', () => {
    expect(parseTransactionGasError(new Error())).toEqual(null);
  });

  test('return errorCode and message for gas price error', () => {
    expect(
      parseTransactionGasError({
        code: 'SERVER_ERROR',
        body: '{"error":{"message":"ERROR","code":-32010}}',
      })
    ).toEqual({ errorCode: TRANSACTION_GAS_PRICE_TOO_LOW, message: 'ERROR' });
  });
});

export class NetworkError extends Error {
  code: string;
  constructor(message: string) {
    super(message);
    this.code = 'NETWORK_ERROR';
  }
}

export class RateLimit extends Error {
  code: number;
  constructor(message: string) {
    super(message);
    this.code = -32005;
  }
}

describe('gatewayErrorMiddleware', () => {
  test('return 503 and UNKNOWN message and code for a normal error', () => {
    expect(gatewayErrorMiddleware(new Error('there was an error'))).toEqual(
      expect.objectContaining({
        message: UNKNOWN_ERROR_MESSAGE,
        httpErrorCode: 503,
        errorCode: UNKNOWN_ERROR_ERROR_CODE,
      })
    );
  });

  test('pass values from HttpException to response error', () => {
    expect(
      gatewayErrorMiddleware(new HttpException(403, 'error', 100))
    ).toEqual(
      expect.objectContaining({
        message: 'error',
        httpErrorCode: 403,
        errorCode: 100,
      })
    );
  });

  test('return NETWORK_ERROR_CODE and NETWORK_ERROR_MESSAGE for network error', () => {
    expect(gatewayErrorMiddleware(new NetworkError('error2'))).toEqual(
      expect.objectContaining({
        message: NETWORK_ERROR_MESSAGE,
        httpErrorCode: 503,
        errorCode: NETWORK_ERROR_CODE,
      })
    );
  });

  test('return Infura RateLimit error', () => {
    expect(gatewayErrorMiddleware(new RateLimit('error3'))).toEqual(
      expect.objectContaining({
        message: RATE_LIMIT_ERROR_MESSAGE,
        httpErrorCode: 503,
        errorCode: RATE_LIMIT_ERROR_CODE,
      })
    );
  });
});
