import { StrategyName } from 'src/composables/useStrategies';

import { $Forms, FileMapContainer } from './form.types';
import { $pureMMForm, pureMMFormFileFieldsMap } from './pureMMForm';

export const $form: $Forms = {
  [StrategyName.PureMarketMaking]: $pureMMForm,
};

export const $fileMap: FileMapContainer = {
  [StrategyName.PureMarketMaking]: pureMMFormFileFieldsMap,
};
