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

describe('isPublicKey', () => {
  it('pass against a well formed public key', () => {
    expect(isPublicKey('HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKEr1')).toEqual(
      true
    );
  });

  it('fail against a string that is too short', () => {
    expect(isPublicKey('HAE1oNnc3XBmPudphRcHhyCvGS')).toEqual(false);
  });

  it('fail against a string that is too long', () => {
    expect(
      isPublicKey(
        'HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKEr1HAE1oNnc3XBmPudphRcHh'
      )
    ).toEqual(false);
  });
});

describe('isPrivateKey', () => {
  it('pass against a well formed private key', () => {
    expect(
      isPrivateKey('HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKEr1')
    ).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isPrivateKey('HAE1oNnc3XBmPudphRcHhyCvGS')).toEqual(false);
  });

  it('fail against a string that is too long', () => {
    expect(
      isPrivateKey(
        'HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKEr1HAE1oNnc3XBmPudphRcHh'
      )
    ).toEqual(false);
  });
});

describe('validatePrivateKey', () => {
  it('valid when req.privateKey is a privateKey', () => {
    expect(
      validatePrivateKey({
        privateKey: 'HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKEr1',
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
        publicKey: 'HAE1oNnc3XBmPudphRcHhyCvGShtgDYtZVzx2MocKEr1',
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
