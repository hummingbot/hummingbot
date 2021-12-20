import {
  isNaturalNumberString,
  isIntegerString,
  isFloatString,
  missingParameter,
  validateTokenSymbols,
} from '../../src/services/validators';

import 'jest-extended';
import { invalidTokenSymbolsError } from '../../src/chains/ethereum/ethereum.validators';

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
        tokenSymbols: ['WETH', 'DAI'],
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
        tokenSymbols: 'WETH',
      })
    ).toEqual([invalidTokenSymbolsError]);
  });
});
