import {
  mkRequestValidator,
  mkValidator,
  RequestValidator,
  Validator,
  validateAmount,
  validateToken,
  validateTokenSymbols,
} from '../../services/validators';
import {
  isAddress,
  validateNonce,
  validateAddress,
} from '../ethereum/ethereum.validators';

export const invalidSpenderError: string =
  'The spender param is not a valid BSC address (0x followed by 40 hexidecimal characters).';

// given a request, look for a key called spender that is 'uniswap' or an Ethereum address
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) => typeof val === 'string' && (val === 'pancakeswap' || isAddress(val))
);

export const validateBSCApproveRequest: RequestValidator = mkRequestValidator([
  validateAddress,
  validateSpender,
  validateToken,
  validateAmount,
  validateNonce,
]);

export const validateBSCAllowancesRequest: RequestValidator =
  mkRequestValidator([validateAddress, validateSpender, validateTokenSymbols]);
