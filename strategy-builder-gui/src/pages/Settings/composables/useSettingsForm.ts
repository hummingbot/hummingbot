import { computed } from 'vue';

import { $settingsForm } from '../stores/settingsForm';

export const useSettingsForm = () => {
  const values = computed(() =>
    Object.keys($settingsForm).reduce(
      (acc, key) => ({ ...acc, [key]: $settingsForm[key].value.value }),
      {},
    ),
  );

  return { settingsForm: $settingsForm, values };
};
