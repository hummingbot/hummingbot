import 'jest-extended';
import {
  invalidPublicKeyError,
  isPublicKey,
  validatePublicKey,
} from '../../../src/chains/solana/solana.validators';
import { missingParameter } from '../../../src/services/validators';

export const publicKey = '3xgEFpNpz1hPU7iHN9P3WPgLTWfZXu6wSUuGw8kigNQr';
export const privateKey =
  '5K23ZvkHuNoakyMKGNoaCvky6a2Yu5yfeoRz2wQLKYAczMKzACN5ZZb9ixu6QcsQvrvh91CNfqu8U1LqC1nvnyfp';

describe('isPublicKey', () => {
  it('pass against a well formed public key', () => {
    expect(isPublicKey(publicKey)).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isPublicKey(publicKey.substring(2))).toEqual(false);
  });

  it('fail against a string that is too long', () => {
    expect(isPublicKey(publicKey + 1)).toEqual(false);
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
    ).toEqual([invalidPublicKeyError]);
  });
});
