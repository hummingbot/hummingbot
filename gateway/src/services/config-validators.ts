import { Validator, mkValidator, isFractionString } from './validators';

export const invalidAllowedSlippage: string =
  'allowedSlippage should be a number or a string of a fraction.';

export const validateAllowedSlippage: Validator = mkValidator(
  'allowedSlippage',
  invalidAllowedSlippage,
  (val) =>
    typeof val === 'number' ||
    (typeof val === 'string' && isFractionString(val))
);
