import { StrategyName } from 'src/composables/useStrategies';

import { $Forms } from './form.types';
import { $pureMMForm, pureMMFormFileFieldsMap } from './pureMMForm';

export const $form: $Forms = {
  [StrategyName.PureMarketMaking]: $pureMMForm,
};

export const $fileMap = {
  [StrategyName.PureMarketMaking]: pureMMFormFileFieldsMap,
};
