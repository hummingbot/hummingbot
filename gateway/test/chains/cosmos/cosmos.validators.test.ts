import {
  invalidCosmosAddressError,
  isValidCosmosAddress,
  validatePublicKey,
} from '../../../src/chains/cosmos/cosmos.validators';
import { missingParameter } from '../../../src/services/validators';
import 'jest-extended';

export const publicKey = 'cosmos1pc8m5m7n0z8xe7sx2tawkvc0v6qkjql83js0dr';
export const privateKey =
  'b6dd181dfa0023013b2479c109e483cb8dc3c20d6fdae6b2443be147c11e5220'; // noqa: mock

describe('isValidCosmosAddress', () => {
  it('pass against a well formed public key', () => {
    expect(isValidCosmosAddress(publicKey)).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isValidCosmosAddress(publicKey.substring(2))).toEqual(false);
  });

  it('fail against a string that is too long', () => {
    expect(isValidCosmosAddress(publicKey + 1)).toEqual(false);
  });
});

describe('validatePublicKey', () => {
  it('valid when req.publicKey is a publicKey', () => {
    expect(
      validatePublicKey({
        address: publicKey,
      })
    ).toEqual([]);
  });

  it('return error when req.publicKey does not exist', () => {
    expect(
      validatePublicKey({
        hello: 'world',
      })
    ).toEqual([missingParameter('address')]);
  });

  it('return error when req.publicKey is invalid', () => {
    expect(
      validatePublicKey({
        address: 'world',
      })
    ).toEqual([invalidCosmosAddressError]);
  });
});
