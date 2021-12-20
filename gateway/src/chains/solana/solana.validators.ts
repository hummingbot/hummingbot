import {
  isNaturalNumberString,
  missingParameter,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../../services/validators';

// invalid parameter errors

export const invalidPrivateKeyError: string =
  'The privateKey param is not a valid Solana private key (64 hexidecimal characters).';

export const invalidSpenderError: string =
  'The spender param is not a valid Solana public key (0x followed by 40 hexidecimal characters).';

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

// test if a string matches the shape of an Solana public key
export const isPublicKey = (str: string): boolean => {
  return /^[a-fA-F0-9]{44}$/.test(str);
};

// test if a string matches the shape of an Solana private key
export const isPrivateKey = (str: string): boolean => {
  return /^[a-fA-F0-9]{44}$/.test(str);
};

// given a request, look for a key called privateKey that is an Solana private key
export const validatePrivateKey: Validator = mkValidator(
  'privateKey',
  invalidPrivateKeyError,
  (val) => typeof val === 'string' && isPrivateKey(val)
);

// given a request, look for a key called spender that is 'uniswap' or an Solana public key
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) => typeof val === 'string' && (val === 'uniswap' || isPublicKey(val))
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

export const validateTxHash: Validator = mkValidator(
  'txHash',
  invalidTxHashError,
  (val) => typeof val === 'string'
);

// request types and corresponding validators

export const validateSolanaBalanceRequest: RequestValidator =
  mkRequestValidator([validatePrivateKey, validateTokenSymbols]);

export const validateSolanaApproveRequest: RequestValidator =
  mkRequestValidator([
    validatePrivateKey,
    validateSpender,
    validateToken,
    validateAmount,
  ]);

export const validateSolanaPollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateSolanaGetTokenRequest: RequestValidator =
  mkRequestValidator([]); // TODO: Implement

export const validateSolanaPostTokenRequest: RequestValidator =
  mkRequestValidator(
    [] // TODO: Implement
  );
