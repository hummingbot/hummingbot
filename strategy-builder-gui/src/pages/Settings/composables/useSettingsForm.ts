import { computed } from 'vue';

import { $settingsForm } from '../stores/settingsForm';
import { FormList } from '../types';

export const useSettingsForm = (form: FormList) => {
  const values = computed(() =>
    Object.keys($settingsForm[form]).reduce(
      (acc, key) => ({ ...acc, [key]: $settingsForm[form][key].value.value }),
      {},
    ),
  );

  return { settingsForm: $settingsForm[form], values };
};
