import { StrategyName } from 'src/composables/useStrategies';

import { $SettingsForm } from './form.types';
import { $pureMMForm } from './pureMMForm';

export const $form: $SettingsForm = {
  [StrategyName.PureMarketMaking]: $pureMMForm,
};
