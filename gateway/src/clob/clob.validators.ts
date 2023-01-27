import {
  isFloatString,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../services/validators';

import {
  isAddress,
  validateChain,
  validateNetwork,
} from '../chains/ethereum/ethereum.validators';

import {
  validateConnector,
  validateAmount,
  validateSide,
} from '../amm/amm.validators';

export const invalidMarkerError: string =
  'The market param is not a valid market. Market should be in {base}-{quote} format.';

export const invalidPriceError: string =
  'The price param may be null or a string of a float or integer number.';

export const invalidWalletError: string =
  'The address param is not a valid address.';

export const invalidOrderIdError: string =
  'The OrderId param is not a valid orderId.';

export const invalidOrderTypeError: string =
  'The orderType specified is invalid. Valid value is either `LIMIT` or `LIMIT_MAKER`';

export const validateMarket: Validator = mkValidator(
  'market',
  invalidMarkerError,
  (val) => typeof val === 'string' && val.split('-').length === 2
);

export const validatePrice: Validator = mkValidator(
  'price',
  invalidPriceError,
  (val) => typeof val === 'string' && isFloatString(val),
  true
);

export const validateWallet: Validator = mkValidator(
  'address',
  invalidWalletError,
  (val) => {
    return (
      typeof val === 'string' &&
      val.length === 66 &&
      isAddress(val.slice(0, 42))
    );
  }
);

export const validateOrderId: Validator = mkValidator(
  'orderId',
  invalidOrderIdError,
  (val) => typeof val === 'string'
);

export const validateOrderType: Validator = mkValidator(
  'orderType',
  invalidOrderTypeError,
  (val) => typeof val === 'string' && (val === 'LIMIT' || val === 'LIMIT_MAKER')
);

const NETWORL_VALIDATIONS = [validateConnector, validateChain, validateNetwork];

export const validateBasicRequest: RequestValidator =
  mkRequestValidator(NETWORL_VALIDATIONS);

export const validateMarketRequest: RequestValidator = mkRequestValidator(
  NETWORL_VALIDATIONS.concat([validateMarket])
);

export const validatePostOrderRequest: RequestValidator = mkRequestValidator(
  NETWORL_VALIDATIONS.concat([
    validateAmount,
    validateWallet,
    validateSide,
    validateOrderType,
    validatePrice,
  ])
);

export const validateOrderRequest: RequestValidator = mkRequestValidator(
  NETWORL_VALIDATIONS.concat([validateOrderId, validateWallet])
);

export const validateBatchOrdersRequest: RequestValidator =
  mkRequestValidator(NETWORL_VALIDATIONS);
