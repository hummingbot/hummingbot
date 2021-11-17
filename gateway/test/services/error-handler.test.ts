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
  InitializationError,
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

class NetworkError extends Error {
  code: string;
  constructor(message: string) {
    super(message);
    this.code = 'NETWORK_ERROR';
  }
}

class ServerError extends Error {
  code: string;
  constructor(message: string) {
    super(message);
    this.code = 'SERVER_ERROR';
  }
}

class TransactionGasError extends Error {
  code: string;
  body: string;
  constructor(message: string) {
    super(message);
    this.code = 'SERVER_ERROR';
    this.body = '{"error":{"code":-32010,"message":"need more gas"}}';
  }
}

class GasPriceTooLowError extends Error {
  code: number;
  constructor(message: string) {
    super(message);
    this.code = -32010;
  }
}

class RateLimit extends Error {
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

  test('return NETWORK_ERROR_CODE and NETWORK_ERROR_MESSAGE for network error', () => {
    expect(
      gatewayErrorMiddleware(new InitializationError('error4', 123))
    ).toEqual(
      expect.objectContaining({
        message: 'error4',
        errorCode: 123,
      })
    );
  });

  test('return NETWORK_ERROR_CODE and NETWORK_ERROR_MESSAGE for server error if not a transaction gas error', () => {
    expect(gatewayErrorMiddleware(new ServerError('error5'))).toEqual(
      expect.objectContaining({
        message: NETWORK_ERROR_MESSAGE,
        httpErrorCode: 503,
        errorCode: NETWORK_ERROR_CODE,
      })
    );
  });

  test('return transaction errorCode and message if it is a transaction gas error', () => {
    expect(gatewayErrorMiddleware(new TransactionGasError('error6'))).toEqual(
      expect.objectContaining({
        message: 'need more gas',
        httpErrorCode: 503,
        errorCode: TRANSACTION_GAS_PRICE_TOO_LOW,
      })
    );
  });

  test('return transaction errorCode and message if it is a transaction gas error', () => {
    expect(gatewayErrorMiddleware(new GasPriceTooLowError('error7'))).toEqual(
      expect.objectContaining({
        errorCode: TRANSACTION_GAS_PRICE_TOO_LOW,
      })
    );
  });
});
