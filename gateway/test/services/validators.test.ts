import {
  isNaturalNumberString,
  isIntegerString,
  isFloatString,
  missingParameter,
  validateTokenSymbols,
  isBase58,
  validateToken,
  validateAmount,
  validateTxHash,
  invalidTokenSymbolsError,
  invalidTokenError,
  invalidAmountError,
  invalidTxHashError,
} from '../../src/services/validators';
import 'jest-extended';

export const tokenSymbols = ['DAI', 'WETH'];
export const txHash =
  '0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d'; // noqa: mock

describe('isNaturalNumberString', () => {
  it('pass against a well formed natural number in a string', () => {
    expect(isNaturalNumberString('12345')).toEqual(true);
  });

  it('fail against a negative number in a string', () => {
    expect(isNaturalNumberString('-12')).toEqual(false);
  });

  it('fail against a non number string', () => {
    expect(isNaturalNumberString('Hello world')).toEqual(false);
  });
});

describe('isIntegerString', () => {
  it('pass against a positive number in a string', () => {
    expect(isIntegerString('12345')).toEqual(true);
  });

  it('pass against a negative number in a string', () => {
    expect(isIntegerString('-12')).toEqual(true);
  });

  it('fail against a non number string', () => {
    expect(isIntegerString('Hello world')).toEqual(false);
  });
});

describe('isFloatString', () => {
  it('pass against a positive number in a string', () => {
    expect(isFloatString('12345')).toEqual(true);

    expect(isFloatString('12.345')).toEqual(true);

    expect(isFloatString('0.45')).toEqual(true);

    expect(isFloatString('0')).toEqual(true);

    expect(isFloatString('0.00001')).toEqual(true);
  });

  it('pass against a negative number in a string', () => {
    expect(isFloatString('-12')).toEqual(true);

    expect(isFloatString('-12.3123')).toEqual(true);

    expect(isFloatString('-0.123')).toEqual(true);
  });

  it('fail against a non number string', () => {
    expect(isFloatString('Hello world')).toEqual(false);
  });
});

describe('validateTokenSymbols', () => {
  it('valid when req.tokenSymbols is an array of strings', () => {
    expect(
      validateTokenSymbols({
        tokenSymbols,
      })
    ).toEqual([]);
  });

  it('return error when req.tokenSymbols does not exist', () => {
    expect(
      validateTokenSymbols({
        hello: 'world',
      })
    ).toEqual([missingParameter('tokenSymbols')]);
  });

  it('return error when req.tokenSymbols is invalid', () => {
    expect(
      validateTokenSymbols({
        tokenSymbols: tokenSymbols[0],
      })
    ).toEqual([invalidTokenSymbolsError]);
  });
});

describe('isBase58', () => {
  it('pass against a well formed Base58', () => {
    expect(isBase58('HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKEr1')).toEqual(
      true
    );
  });

  it('fail against a string that has non-Base58 characters', () => {
    expect(isBase58('HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKErI')).toEqual(
      false
    );
  });
});

describe('validateToken', () => {
  it('valid when req.token is a string', () => {
    expect(
      validateToken({
        token: 'DAI',
      })
    ).toEqual([]);

    expect(
      validateToken({
        token: 'WETH',
      })
    ).toEqual([]);
  });

  it('return error when req.token does not exist', () => {
    expect(
      validateToken({
        hello: 'world',
      })
    ).toEqual([missingParameter('token')]);
  });

  it('return error when req.token is invalid', () => {
    expect(
      validateToken({
        token: 123,
      })
    ).toEqual([invalidTokenError]);
  });
});

describe('validateAmount', () => {
  it('valid when req.amount is a string of an integer', () => {
    expect(
      validateAmount({
        amount: '0',
      })
    ).toEqual([]);
    expect(
      validateAmount({
        amount: '9999999999999999999999',
      })
    ).toEqual([]);
  });

  it('valid when req.amount does not exist', () => {
    expect(
      validateAmount({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.amount is invalid', () => {
    expect(
      validateAmount({
        amount: 'WETH',
      })
    ).toEqual([invalidAmountError]);
  });
});

describe('validateTxHash', () => {
  it('valid when req.txHash is a string', () => {
    expect(validateTxHash({ txHash })).toEqual([]);
  });

  it('invalid when req.txHash does not exist', () => {
    expect(
      validateTxHash({
        hello: 'world',
      })
    ).toEqual([missingParameter('txHash')]);
  });

  it('return error when req.txHash is invalid', () => {
    expect(
      validateTxHash({
        txHash: 123,
      })
    ).toEqual([invalidTxHashError]);
  });
});
