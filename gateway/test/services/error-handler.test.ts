import {
  parseTransactionGasError,
  TRANSACTION_GAS_PRICE_TOO_LOW,
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
