import {
  isNaturalNumberString,
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
  validateToken,
  validateAmount,
} from '../../services/validators';

// invalid parameter errors

export const invalidAddressError: string =
  'The address param is not a valid Ethereum private key (64 hexidecimal characters).';

export const invalidSpenderError: string =
  'The spender param is not a valid Ethereum address (0x followed by 40 hexidecimal characters).';

export const invalidNonceError: string =
  'If nonce is included it must be a non-negative integer.';

export const invalidMaxFeePerGasError: string =
  'If maxFeePerGas is included it must be a string of a non-negative integer.';

export const invalidMaxPriorityFeePerGasError: string =
  'If maxPriorityFeePerGas is included it must be a string of a non-negative integer.';

export const invalidChainError: string = 'The chain param is not a string.';

export const invalidNetworkError: string = 'The network param is not a string.';

// test if a string matches the shape of an Ethereum address
export const isAddress = (str: string): boolean => {
  return /^0x[a-fA-F0-9]{40}$/.test(str);
};

// given a request, look for a key called address that is an Ethereum wallet
export const validateAddress: Validator = mkValidator(
  'address',
  invalidAddressError,
  (val) => typeof val === 'string' && isAddress(val)
);

// given a request, look for a key called spender that is 'uniswap' or an Ethereum address
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) =>
    typeof val === 'string' &&
    (val === 'uniswap' ||
      val === 'perp' ||
      val === 'uniswapLP' ||
      val === 'pangolin' ||
      val === 'traderjoe' ||
      val === 'sushiswap' ||
      val === 'viperswap' ||
      val === 'openocean' ||
      val === 'quickswap' ||
      val === 'defikingdoms' ||
      val === 'defira' ||
      val === 'mad_meerkat' ||
      val === 'vvs' ||
      val === 'pancakeswap' ||
      isAddress(val))
);

export const validateNonce: Validator = mkValidator(
  'nonce',
  invalidNonceError,
  (val) =>
    typeof val === 'undefined' ||
    (typeof val === 'number' && val >= 0 && Number.isInteger(val)),
  true
);

export const validateMaxFeePerGas: Validator = mkValidator(
  'maxFeePerGas',
  invalidMaxFeePerGasError,
  (val) => typeof val === 'string' && isNaturalNumberString(val),
  true
);

export const validateMaxPriorityFeePerGas: Validator = mkValidator(
  'maxPriorityFeePerGas',
  invalidMaxPriorityFeePerGasError,
  (val) => typeof val === 'string' && isNaturalNumberString(val),
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

export const validateNonceRequest: RequestValidator = mkRequestValidator([
  validateAddress,
]);

export const validateAllowancesRequest: RequestValidator = mkRequestValidator([
  validateAddress,
  validateSpender,
  validateTokenSymbols,
]);

export const validateBalanceRequest: RequestValidator = mkRequestValidator([
  validateAddress,
  validateTokenSymbols,
]);

export const validateApproveRequest: RequestValidator = mkRequestValidator([
  validateAddress,
  validateSpender,
  validateToken,
  validateAmount,
  validateNonce,
  validateMaxFeePerGas,
  validateMaxPriorityFeePerGas,
]);

export const validateCancelRequest: RequestValidator = mkRequestValidator([
  validateNonce,
  validateAddress,
]);
