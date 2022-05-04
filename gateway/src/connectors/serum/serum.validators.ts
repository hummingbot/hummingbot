import {StatusCodes} from "http-status-codes";
import {
  isBase58,
  isFloatString,
  isNaturalNumberString,
  mkRequestValidator,
  mkValidator,
  RequestValidator,
  Validator
} from '../../services/validators';
import {OrderSide, OrderType} from "./serum.types";

export const validateOrderClientId: Validator = mkValidator(
  'id',
  (value) => `Invalid client id (${value}), it needs to be in big number format.`,
  (target) => isNaturalNumberString(target),
  true
);

export const validateOrderMarketName: Validator = mkValidator(
  'marketName',
  (value) => `Invalid market name (${value}).`,
  (target) => target.trim().length,
  false
);

export const validateOrderOwnerAddress: Validator = mkValidator(
  'ownerAddress',
  (value) => `Invalid owner address (${value}).`,
  (target) => isBase58(target),
  false
);

export const validateOrderSide: Validator = mkValidator(
  'side',
  (value) => `Invalid order side (${value}).`,
  (target) => Object.values(OrderSide).map(i => i.toLowerCase()).includes(target.toLowerCase()),
  false
);

export const validateOrderPrice: Validator = mkValidator(
  'price',
  (value) => `Invalid order price (${value}).`,
  (target) => typeof target === 'number' || isFloatString(target),
  false
);

export const validateOrderAmount: Validator = mkValidator(
  'amount',
  (value) => `Invalid order amount (${value}).`,
  (target) => typeof target === 'number' || isFloatString(target),
  false
);

export const validateOrderType: Validator = mkValidator(
  'type',
  (value) => `Invalid  order type (${value}).`,
  (target) => Object.values(OrderType).map(item => item.toLowerCase()).includes(target.toLowerCase()),
  true
);

export const validateCreateOrder: RequestValidator = mkRequestValidator([
  validateOrderClientId,
  validateOrderMarketName,
  validateOrderOwnerAddress,
  validateOrderSide,
  validateOrderPrice,
  validateOrderAmount,
  validateOrderType
], StatusCodes.BAD_REQUEST);
