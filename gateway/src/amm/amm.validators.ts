import {
  isFloatString,
  isFractionString,
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

import { FeeAmount } from '@uniswap/v3-sdk';

export const invalidConnectorError: string =
  'The connector param is not a string.';

export const invalidQuoteError: string = 'The quote param is not a string.';

export const invalidBaseError: string = 'The base param is not a string.';

export const invalidTokenError: string =
  'One of the token params is not a string.';

export const invalidAmountError: string =
  'The amount param must be a string of a non-negative integer.';

export const invalidSideError: string =
  'The side param must be a string of "BUY" or "SELL".';

export const invalidPerpSideError: string =
  'The side param must be a string of "LONG" or "SHORT".';

export const invalidFeeTier: string = 'Incorrect fee tier';

export const invalidLimitPriceError: string =
  'The limitPrice param may be null or a string of a float or integer number.';

export const invalidLPPriceError: string =
  'One of the LP prices may be null or a string of a float or integer number.';

export const invalidTokenIdError: string =
  'If tokenId is included it must be a non-negative integer.';

export const invalidTimeError: string =
  'Period or interval has to be a non-negative integer.';

export const invalidDecreasePercentError: string =
  'If decreasePercent is included it must be a non-negative integer.';

export const invalidAllowedSlippageError: string =
  'The allowedSlippage param may be null or a string of a fraction.';

export const validateConnector: Validator = mkValidator(
  'connector',
  invalidConnectorError,
  (val) => typeof val === 'string'
);

export const validateQuote: Validator = mkValidator(
  'quote',
  invalidQuoteError,
  (val) => typeof val === 'string'
);

export const validateBase: Validator = mkValidator(
  'base',
  invalidBaseError,
  (val) => typeof val === 'string'
);

export const validateToken0: Validator = mkValidator(
  'token0',
  invalidTokenError,
  (val) => typeof val === 'string'
);

export const validateToken1: Validator = mkValidator(
  'token1',
  invalidTokenError,
  (val) => typeof val === 'string'
);

export const validateAmount: Validator = mkValidator(
  'amount',
  invalidAmountError,
  (val) => typeof val === 'string' && isFloatString(val)
);

export const validateAmount0: Validator = mkValidator(
  'amount0',
  invalidAmountError,
  (val) => typeof val === 'string'
);

export const validateAmount1: Validator = mkValidator(
  'amount1',
  invalidAmountError,
  (val) => typeof val === 'string'
);

export const validateSide: Validator = mkValidator(
  'side',
  invalidSideError,
  (val) => typeof val === 'string' && (val === 'BUY' || val === 'SELL')
);

export const validatePerpSide: Validator = mkValidator(
  'side',
  invalidPerpSideError,
  (val) => typeof val === 'string' && (val === 'LONG' || val === 'SHORT')
);

export const validateFee: Validator = mkValidator(
  'fee',
  invalidFeeTier,
  (val) =>
    typeof val === 'string' &&
    Object.keys(FeeAmount).includes(val.toUpperCase())
);

export const validateLowerPrice: Validator = mkValidator(
  'lowerPrice',
  invalidLPPriceError,
  (val) => typeof val === 'string' && isFloatString(val),
  true
);

export const validateUpperPrice: Validator = mkValidator(
  'upperPrice',
  invalidLPPriceError,
  (val) => typeof val === 'string' && isFloatString(val),
  true
);

export const validateLimitPrice: Validator = mkValidator(
  'limitPrice',
  invalidLimitPriceError,
  (val) => typeof val === 'string' && isFloatString(val),
  true
);

export const validateTokenId: Validator = mkValidator(
  'tokenId',
  invalidTokenIdError,
  (val) =>
    typeof val === 'undefined' ||
    (typeof val === 'number' && val >= 0 && Number.isInteger(val)),
  true
);

export const validatePeriod: Validator = mkValidator(
  'period',
  invalidTimeError,
  (val) => typeof val === 'number' && val >= 0 && Number.isInteger(val),
  true
);

export const validateInterval: Validator = mkValidator(
  'interval',
  invalidTimeError,
  (val) => typeof val === 'number' && val >= 0 && Number.isInteger(val),
  true
);

export const validateDecreasePercent: Validator = mkValidator(
  'decreasePercent',
  invalidDecreasePercentError,
  (val) =>
    typeof val === 'undefined' ||
    (typeof val === 'number' && val >= 0 && Number.isFinite(val)),
  true
);

export const validateAllowedSlippage: Validator = mkValidator(
  'allowedSlippage',
  invalidAllowedSlippageError,
  (val) => typeof val === 'string' && isFractionString(val),
  true
);

export const validatePriceRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  validateQuote,
  validateBase,
  validateAmount,
  validateSide,
  validateAllowedSlippage,
]);

export const validateTradeRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  validateQuote,
  validateBase,
  validateAmount,
  validateSide,
  validateLimitPrice,
  validateNonce,
  validateMaxFeePerGas,
  validateMaxPriorityFeePerGas,
  validateAllowedSlippage,
]);

export const validatePerpPositionRequest: RequestValidator = mkRequestValidator(
  [
    validateConnector,
    validateChain,
    validateNetwork,
    validateQuote,
    validateBase,
    validateAddress,
  ]
);

export const validatePerpBalanceRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  validateAddress,
]);

export const validatePerpMarketStatusRequest: RequestValidator =
  mkRequestValidator([
    validateConnector,
    validateChain,
    validateNetwork,
    validateQuote,
    validateBase,
  ]);

export const validatePerpPairsRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
]);

export const validatePerpOpenTradeRequest: RequestValidator =
  mkRequestValidator([
    validateConnector,
    validateChain,
    validateNetwork,
    validateQuote,
    validateBase,
    validateAmount,
    validateAddress,
    validatePerpSide,
    validateNonce,
    validateAllowedSlippage,
  ]);

export const validatePerpCloseTradeRequest: RequestValidator =
  mkRequestValidator([
    validateConnector,
    validateChain,
    validateNetwork,
    validateQuote,
    validateBase,
    validateAddress,
    validateNonce,
    validateAllowedSlippage,
  ]);

export const validateEstimateGasRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
]);

export const validateAddLiquidityRequest: RequestValidator = mkRequestValidator(
  [
    validateConnector,
    validateChain,
    validateNetwork,
    validateToken0,
    validateToken1,
    validateAmount0,
    validateAmount1,
    validateAddress,
    validateFee,
    validateUpperPrice,
    validateLowerPrice,
    validateTokenId,
    validateNonce,
    validateMaxFeePerGas,
    validateMaxPriorityFeePerGas,
  ]
);

export const validateRemoveLiquidityRequest: RequestValidator =
  mkRequestValidator([
    validateConnector,
    validateChain,
    validateNetwork,
    validateAddress,
    validateTokenId,
    validateDecreasePercent,
    validateNonce,
    validateMaxFeePerGas,
    validateMaxPriorityFeePerGas,
  ]);

export const validateCollectFeeRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  validateAddress,
  validateTokenId,
  validateNonce,
  validateMaxFeePerGas,
  validateMaxPriorityFeePerGas,
]);

export const validatePositionRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  validateTokenId,
]);

export const validatePoolPriceRequest: RequestValidator = mkRequestValidator([
  validateConnector,
  validateChain,
  validateNetwork,
  validateToken0,
  validateToken1,
  validateFee,
  validateInterval,
  validatePeriod,
]);
