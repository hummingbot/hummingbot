import {mkRequestValidator, mkValidator, RequestValidator} from '../../services/validators';

// TODO fill or remove these validators!!!
export const requestExample: RequestValidator = mkRequestValidator([]);

export const itemExample: RequestValidator = mkValidator(
  'key',
  'Error message.',
  (target) => target,
  false
);
