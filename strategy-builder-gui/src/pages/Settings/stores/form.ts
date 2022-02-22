import { StrategyName } from 'src/composables/useStrategies';

import { $SettingsForm } from './form.types';
import { $pureMMForm } from './pureMMForm';

export const $settingsForm: $SettingsForm = {
  [StrategyName.PureMarketMaking]: $pureMMForm,
};
