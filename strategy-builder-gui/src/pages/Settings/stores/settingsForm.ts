import { StrategyName } from '../../../stores/strategies';
import { $SettingsForm } from './form.types';
import { $pureMMForm } from './pureMMForm';

export const $settingsForm: $SettingsForm = {
  [StrategyName.PureMarketMaking]: $pureMMForm,
};
