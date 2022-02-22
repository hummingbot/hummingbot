import { StrategyName } from 'src/composables/useStrategies';

import { $Forms } from './form.types';
import { $pureMMForm } from './pureMMForm';

export const $form: $Forms = {
  [StrategyName.PureMarketMaking]: $pureMMForm,
};
