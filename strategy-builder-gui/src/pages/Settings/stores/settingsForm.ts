import { $SettingsForm, FormList } from '../types';
import { $pureMMForm } from './pureMMForm';

export const $settingsForm: $SettingsForm = {
  [FormList.PureMarketMaking]: {
    ...$pureMMForm,
  },
};
