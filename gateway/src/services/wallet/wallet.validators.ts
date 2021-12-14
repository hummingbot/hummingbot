import {
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../validators';

import { validatePrivateKey } from '../../chains/ethereum/ethereum.validators';

export const invalidChainNameError: string =
  'chainName must be "ethereum" or "avalanche"';

export const invalidAddressError: string = 'address must be a string';

export const validateChainName: Validator = mkValidator(
  'chainName',
  invalidChainNameError,
  (val) =>
    typeof val === 'string' && (val === 'ethereum' || val === 'avalanche')
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
