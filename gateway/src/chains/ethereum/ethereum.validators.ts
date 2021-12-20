import {
  isNaturalNumberString,
  mkValidator,
  mkRequestValidator,
  validateTokenSymbols,
  RequestValidator,
  Validator,
} from '../../services/validators';

// invalid parameter errors

export const invalidPrivateKeyError: string =
  'The privateKey param is not a valid Ethereum private key (64 hexidecimal characters).';

export const invalidSpenderError: string =
  'The spender param is not a valid Ethereum public key (0x followed by 40 hexidecimal characters).';

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

// test if a string matches the shape of an Ethereum public key
export const isPublicKey = (str: string): boolean => {
  return /^0x[a-fA-F0-9]{40}$/.test(str);
};

// test if a string matches the shape of an Ethereum private key
export const isPrivateKey = (str: string): boolean => {
  return /^(0x)?[a-fA-F0-9]{64}$/.test(str);
};

// given a request, look for a key called privateKey that is an Ethereum private key
export const validatePrivateKey: Validator = mkValidator(
  'privateKey',
  invalidPrivateKeyError,
  (val) => typeof val === 'string' && isPrivateKey(val)
);

// given a request, look for a key called spender that is 'uniswap' or an Ethereum public key
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) => typeof val === 'string' && (val === 'uniswap' || isPublicKey(val))
);

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

export const validateEthereumNonceRequest: RequestValidator =
  mkRequestValidator([validatePrivateKey]);

export const validateEthereumAllowancesRequest: RequestValidator =
  mkRequestValidator([
    validatePrivateKey,
    validateSpender,
    validateTokenSymbols,
  ]);

export const validateEthereumBalanceRequest: RequestValidator =
  mkRequestValidator([validatePrivateKey, validateTokenSymbols]);

export const validateEthereumApproveRequest: RequestValidator =
  mkRequestValidator([
    validatePrivateKey,
    validateSpender,
    validateToken,
    validateAmount,
    validateNonce,
    validateMaxFeePerGas,
    validateMaxPriorityFeePerGas,
  ]);

export const validateEthereumPollRequest: RequestValidator = mkRequestValidator(
  [validateTxHash]
);

export const validateEthereumCancelRequest: RequestValidator =
  mkRequestValidator([validateNonce, validatePrivateKey]);
