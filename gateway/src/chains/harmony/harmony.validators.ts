import {
  isNaturalNumberString,
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
  validateToken,
  validateAmount,
  validateTxHash,
} from '../../services/validators';

import { isValidAddress } from '@harmony-js/utils';

// invalid parameter errors

export const invalidAddressError: string =
  'The address param is not a valid Ethereum private key (64 hexidecimal characters).';

export const invalidSpenderError: string =
  'The spender param is not a valid Ethereum public key (0x followed by 40 hexidecimal characters).';

export const invalidNonceError: string =
  'If nonce is included it must be a non-negative integer.';

export const invalidMaxFeePerGasError: string =
  'If maxFeePerGas is included it must be a string of a non-negative integer.';

export const invalidMaxPriorityFeePerGasError: string =
  'If maxPriorityFeePerGas is included it must be a string of a non-negative integer.';

// given a request, look for a key called address that is an Ethereum private key
export const validateAddress: Validator = mkValidator(
  'address',
  invalidAddressError,
  (val) => typeof val === 'string' && isValidAddress(val)
);

// given a request, look for a key called spender that is 'uniswap' or an Ethereum public key
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) =>
    typeof val === 'string' &&
    (val === 'sushiswap' ||
      val === 'viperswap' ||
      val === 'defikingdoms' ||
      val === 'defira' ||
      isValidAddress(val))
);

export const validateNonce: Validator = mkValidator(
  'nonce',
  invalidNonceError,
  (val) => typeof val === 'number' && val >= 0 && Number.isInteger(val),
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

export const validatePollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateCancelRequest: RequestValidator = mkRequestValidator([
  validateNonce,
  validateAddress,
]);
