import {
  validateSpender,
  invalidSpenderError,
  validatePolygonApproveRequest,
} from '../../../src/chains/polygon/polygon.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('validateSpender', () => {
  it('valid when req.spender is a publicKey', () => {
    expect(
      validateSpender({
        spender: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      })
    ).toEqual([]);
  });

  it("valid when req.spender is a 'uniswap'", () => {
    expect(
      validateSpender({
        spender: 'uniswap',
      })
    ).toEqual([]);
  });

  it('return error when req.spender does not exist', () => {
    expect(
      validateSpender({
        hello: 'world',
      })
    ).toEqual([missingParameter('spender')]);
  });

  it('return error when req.spender is invalid', () => {
    expect(
      validateSpender({
        spender: 'world',
      })
    ).toEqual([invalidSpenderError]);
  });
});

describe('validatePolygonApproveRequest', () => {
  it('valid when req.spender is a publicKey', () => {
    expect(
      validatePolygonApproveRequest({
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        spender: 'uniswap',
        token: 'DAI',
        amount: '1000000',
        nonce: 0,
      })
    ).toEqual(undefined);
  });
});
