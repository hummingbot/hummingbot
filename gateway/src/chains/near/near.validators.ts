import {
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../../services/validators';

// invalid parameter errors

export const invalidAddressError: string =
  'The address param is not a valid Near private key.';

export const invalidSpenderError: string =
  'The spender param is not a valid Near address.';

export const invalidNonceError: string =
  'If nonce is included it must be a non-negative integer.';

export const invalidChainError: string = 'The chain param is not a string.';

export const invalidNetworkError: string = 'The network param is not a string.';

// given a request, look for a key called address that is an Ethereum wallet
export const validateAddress: Validator = mkValidator(
  'address',
  invalidAddressError,
  (val) => typeof val === 'string'
);

// given a request, look for a key called spender that has a string value
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) => typeof val === 'string'
);

export const validateNonce: Validator = mkValidator(
  'nonce',
  invalidNonceError,
  (val) =>
    typeof val === 'undefined' ||
    (typeof val === 'number' && val >= 0 && Number.isInteger(val)),
  true
);

export const validateChain: Validator = mkValidator(
  'chain',
  invalidChainError,
  (val) => typeof val === 'string'
);

export const validateNetwork: Validator = mkValidator(
  'network',
  invalidNetworkError,
  (val) => typeof val === 'string'
);

// request types and corresponding validators

export const validateBalanceRequest: RequestValidator = mkRequestValidator([
  validateAddress,
  validateTokenSymbols,
]);
