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
  'The spender param is invalid xdc address (0x or xdc followed by 40 hexidecimal characters).';

// given a request, look for a key called spender that is 'xdcswap' or an Ethereum address
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) => typeof val === 'string' && (val === 'xdcswap' || isAddress(val))
);

export const validateXdcApproveRequest: RequestValidator =
  mkRequestValidator([
    validateAddress,
    validateSpender,
    validateToken,
    validateAmount,
    validateNonce,
  ]);

export const validateXdcAllowancesRequest: RequestValidator =
  mkRequestValidator([
    validateAddress,
    validateSpender,
    validateTokenSymbols
  ]);
