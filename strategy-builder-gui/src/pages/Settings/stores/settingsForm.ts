import { $SettingsForm, StrategyName } from '../types';
import { $pureMMForm } from './pureMMForm';

export const $settingsForm: $SettingsForm = {
  [StrategyName.PureMarketMaking]: {
    ...$pureMMForm,
  },
};
