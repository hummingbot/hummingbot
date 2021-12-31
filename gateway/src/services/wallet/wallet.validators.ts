import {
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../validators';

export const invalidPrivateKeyError: string =
  'The privateKey param is not a valid Ethereum private key (64 hexidecimal characters).';

// test if a string matches the shape of an Ethereum private key
export const isPrivateKey = (str: string): boolean => {
  return /^(0x)?[a-fA-F0-9]{64}$/.test(str);
};

// given a request, look for a key called privateKey that is an Ethereum private key
// TODO: Case for Solana private keys
export const validatePrivateKey: Validator = mkValidator(
  'privateKey',
  invalidPrivateKeyError,
  (val) => typeof val === 'string' && isPrivateKey(val)
);

export const invalidChainNameError: string =
  'chainName must be "ethereum", "avalanche" or "solana';

export const invalidAddressError: string = 'address must be a string';

export const validateChainName: Validator = mkValidator(
  'chainName',
  invalidChainNameError,
  (val) =>
    typeof val === 'string' &&
    (val === 'ethereum' || val === 'avalanche' || val === 'solana')
);

export const validateAddress: Validator = mkValidator(
  'address',
  invalidAddressError,
  (val) => typeof val === 'string'
);

export const validateAddWalletRequest: RequestValidator = mkRequestValidator([
  validatePrivateKey,
  validateChainName,
]);

export const validateRemoveWalletRequest: RequestValidator = mkRequestValidator(
  [validateAddress, validateChainName]
);
