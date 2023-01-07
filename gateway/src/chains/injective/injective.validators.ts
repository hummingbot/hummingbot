import {
  isFloatString,
  invalidAmountError,
  mkValidator,
  Validator,
  mkRequestValidator,
  RequestValidator,
} from '../../services/validators';
import { validateNetwork } from '../ethereum/ethereum.validators';

export const invalidTxHashError: string = 'The txHash param must be a string.';

export const invalidTokenError: string = 'The token param must be a string.';

export const validateTxHash: Validator = mkValidator(
  'txHash',
  invalidTxHashError,
  (val) => typeof val === 'string'
);

export const invalidAddressError: string =
  'The address param must be a non-empty string.';

// given a request, look for a key called address that is an Ethereum wallet
export const validateAddress: Validator = mkValidator(
  'address',
  invalidAddressError,
  (val) => typeof val === 'string'
);

export const validateBalanceRequest: RequestValidator = mkRequestValidator([
  validateNetwork,
  validateAddress,
]);

export const validatePollRequest: RequestValidator = mkRequestValidator([
  validateNetwork,
  validateTxHash,
]);

export const validateAmount: Validator = mkValidator(
  'amount',
  invalidAmountError,
  (val) => typeof val === 'string' && isFloatString(val)
);

export const validateToken: Validator = mkValidator(
  'token',
  invalidTokenError,
  (val) => typeof val === 'string'
);

export const validateTransferToSubAccountRequest = mkRequestValidator([
  validateNetwork,
  validateAddress,
  validateAmount,
  validateToken,
]);

export const validateTransferToBankAccountRequest =
  validateTransferToSubAccountRequest;
