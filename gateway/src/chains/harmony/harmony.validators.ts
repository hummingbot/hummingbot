import {
  isNaturalNumberString,
  missingParameter,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../../services/validators';

// invalid parameter errors

export const invalidAddressError: string =
  'The address param is not a valid Harmony private key (64 hexidecimal characters).';

export const invalidSpenderError: string =
  'The spender param is not a valid Harmony public key (0x followed by 40 hexidecimal characters).';

export const invalidTokenSymbolsError: string =
  'The tokenSymbols param should be an array of strings.';

export const invalidTokenError: string = 'The token param should be a string.';

export const invalidAmountError: string =
  'If amount is included it must be a string of a non-negative integer.';

export const invalidNonceError: string =
  'If nonce is included it must be a non-negative integer.';

export const invalidMaxFeePerGasError: string =
  'If maxFeePerGas is included it must be a string of a non-negative integer.';

export const invalidMaxPriorityFeePerGasError: string =
  'If maxPriorityFeePerGas is included it must be a string of a non-negative integer.';

export const invalidTxHashError: string = 'The txHash param must be a string.';

// test if a string matches the shape of an Harmony public key
export const isAddress = (str: string): boolean => {
  return /^0x[a-fA-F0-9]{40}$/.test(str);
};

// given a request, look for a key called address that is an Harmony private key
export const validateAddress: Validator = mkValidator(
  'address',
  invalidAddressError,
  (val) => typeof val === 'string' && isAddress(val)
);

// given a request, look for a key called spender that is 'uniswap' or an Harmony public key
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) => typeof val === 'string' && (val === 'uniswap' || isAddress(val))
);

// confirm that tokenSymbols is an array of strings
export const validateTokenSymbols: Validator = (req: any) => {
  const errors: Array<string> = [];
  if (req.tokenSymbols) {
    if (Array.isArray(req.tokenSymbols)) {
      req.tokenSymbols.forEach((symbol: any) => {
        if (typeof symbol !== 'string') {
          errors.push(invalidTokenSymbolsError);
        }
      });
    } else {
      errors.push(invalidTokenSymbolsError);
    }
  } else {
    errors.push(missingParameter('tokenSymbols'));
  }
  return errors;
};

// confirm that token is a string
export const validateToken: Validator = mkValidator(
  'token',
  invalidTokenError,
  (val) => typeof val === 'string'
);

// if amount exists, confirm that it is a string of a natural number
export const validateAmount: Validator = mkValidator(
  'amount',
  invalidAmountError,
  (val) => typeof val === 'string' && isNaturalNumberString(val),
  true
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

export const validateTxHash: Validator = mkValidator(
  'txHash',
  invalidTxHashError,
  (val) => typeof val === 'string'
);

// request types and corresponding validators

export const validateHarmonyNonceRequest: RequestValidator = mkRequestValidator(
  [validateAddress]
);

export const validateHarmonyAllowancesRequest: RequestValidator =
  mkRequestValidator([validateAddress, validateSpender, validateTokenSymbols]);

export const validateHarmonyBalanceRequest: RequestValidator =
  mkRequestValidator([validateAddress, validateTokenSymbols]);

export const validateHarmonyApproveRequest: RequestValidator =
  mkRequestValidator([
    validateAddress,
    validateSpender,
    validateToken,
    validateAmount,
    validateNonce,
    validateMaxFeePerGas,
    validateMaxPriorityFeePerGas,
  ]);

export const validateHarmonyPollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateHarmonyCancelRequest: RequestValidator =
  mkRequestValidator([validateNonce, validateAddress]);
