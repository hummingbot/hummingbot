import {
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../services/validators';

import {
  validateChain,
  validateNetwork,
  validateNonce,
  validateAddress,
  validateMaxFeePerGas,
  validateMaxPriorityFeePerGas,
} from '../chains/ethereum/ethereum.validators';

export const invalidConnectorError: string =
  'The connector param is not a string.';

export const validateConnector: Validator = mkValidator(
  'connector',
  invalidConnectorError,
  (val) => typeof val === 'string'
);

export const validatePriceRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  // add additional validators here
]);

export const validateTradeRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  validateNonce,
  validateMaxFeePerGas,
  validateMaxPriorityFeePerGas,
  // add additional validators here
]);

export const validateEstimateGasRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
]);
