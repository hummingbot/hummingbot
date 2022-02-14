import { computed } from 'vue';

import { $settingsForm } from '../stores/settingsForm';

export const useSettingsForm = () => {
  const { inputs, counters, selects, toggles } = $settingsForm;
  const formObject = { ...inputs, ...selects, ...counters, ...toggles };

  const values = computed(() =>
    Object.keys(formObject).reduce(
      (acc, key) => ({ ...acc, [key]: formObject[key].value.value }),
      {},
    ),
  );

  return { settingsForm: $settingsForm, values };
};
