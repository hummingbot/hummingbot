/* WIP */
import {
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
  validateTxHash,
} from '../../services/validators';
import { normalizeBech32 } from '@cosmjs/encoding';

export const invalidCosmosAddressError: string =
  'The spender param is not a valid Cosmos address. (Bech32 format)';

export const isValidCosmosAddress = (str: string): boolean => {
  const normalized = normalizeBech32(str);

  if (normalized) {
    return true;
  }

  return false;
};

// given a request, look for a key called address that is a Cosmos address
export const validatePublicKey: Validator = mkValidator(
  'address',
  invalidCosmosAddressError,
  (val) => typeof val === 'string' && isValidCosmosAddress(val)
);

// request types and corresponding validators

export const validateCosmosBalanceRequest: RequestValidator =
  mkRequestValidator([validatePublicKey, validateTokenSymbols]);

export const validateCosmosPollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);
