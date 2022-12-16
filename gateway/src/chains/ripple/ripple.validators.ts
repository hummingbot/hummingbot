import {
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
  isBase58,
  validateTxHash,
  validateToken,
} from '../../services/validators';

// invalid parameter errors
export const invalidRippleAddressError: string =
  'The spender param is not a valid Ripple address (20 bytes, base 58 encoded).';

export const invalidRipplePrivateKeyError: string =
  'The privateKey param is not a valid Ripple seed key (16 bytes, base 58 encoded).';

// test if a string matches the shape of an Ripple address
export const isRippleAddress = (str: string): boolean => {
  return isBase58(str) && str.length <= 35 && str.charAt(0) == 'r';
};

// test if a string matches the shape of an Ripple seed key
export const isRippleSeedKey = (str: string): boolean => {
  return isBase58(str) && str.length <= 29 && str.charAt(0) == 's';
};

// given a request, look for a key called address that is an Solana address
export const validateRippleAddress: Validator = mkValidator(
  'address',
  invalidRippleAddressError,
  (val) => typeof val === 'string' && isRippleAddress(val)
);

// request types and corresponding validators

export const validateRippleBalanceRequest: RequestValidator =
  mkRequestValidator([validateRippleAddress, validateTokenSymbols]);

export const validateRipplePollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateRippleGetTokenRequest: RequestValidator =
  mkRequestValidator([validateToken, validateRippleAddress]);

export const validateRipplePostTokenRequest: RequestValidator =
  mkRequestValidator([validateToken, validateRippleAddress]);
