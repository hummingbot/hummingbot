import {
  isPrivateKey,
  isPublicKey,
  validatePrivateKey,
  invalidPrivateKeyError,
  validatePublicKey,
  invalidPublicKeyError,
} from '../../../src/chains/solana/solana.validators';
import { missingParameter } from '../../../src/services/validators';
import 'jest-extended';

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

describe('isPrivateKey', () => {
  it('pass against a well formed private key', () => {
    expect(isPrivateKey(privateKey)).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isPrivateKey(privateKey.substring(2))).toEqual(false);
  });

  it('fail against a string that is too long', () => {
    expect(isPrivateKey(privateKey + 1)).toEqual(false);
  });
});

describe('validatePrivateKey', () => {
  it('valid when req.privateKey is a privateKey', () => {
    expect(
      validatePrivateKey({
        privateKey,
      })
    ).toEqual([]);
  });

  it('return error when req.privateKey does not exist', () => {
    expect(
      validatePrivateKey({
        hello: 'world',
      })
    ).toEqual([missingParameter('privateKey')]);
  });

  it('return error when req.privateKey is invalid', () => {
    expect(
      validatePrivateKey({
        privateKey: 'world',
      })
    ).toEqual([invalidPrivateKeyError]);
  });
});

describe('validatePublicKey', () => {
  it('valid when req.publicKey is a publicKey', () => {
    expect(
      validatePublicKey({
        publicKey,
      })
    ).toEqual([]);
  });

  it('return error when req.publicKey does not exist', () => {
    expect(
      validatePublicKey({
        hello: 'world',
      })
    ).toEqual([missingParameter('publicKey')]);
  });

  it('return error when req.publicKey is invalid', () => {
    expect(
      validatePublicKey({
        publicKey: 'world',
      })
    ).toEqual([invalidPublicKeyError]);
  });
});
