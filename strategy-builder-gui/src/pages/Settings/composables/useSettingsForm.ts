import { computed } from 'vue';

import { $settingsForm } from '../stores/settingsForm';

export const useSettingsForm = () => {
  const values = computed(() =>
    Object.keys($settingsForm).reduce((acc, key) => {
      const value =
        typeof $settingsForm[key].value.value === 'object'
          ? JSON.parse(JSON.stringify($settingsForm[key].value.value))
          : $settingsForm[key].value.value;
      return { ...acc, [key]: value };
    }, {}),
  );

  return { settingsForm: $settingsForm, values };
};
