import { StrategyName } from 'src/composables/useStrategies';
import { computed, Ref } from 'vue';

import { $form } from '../stores/form';
import { FormValue } from '../stores/form.types';

export { BtnToggleType } from '../stores/form.types';

const fixValue = (value: number | string | boolean) => {
  if (typeof value === 'number') {
    return Number(value.toFixed(2));
  }

  return value;
};

export const useForm = (strategyName: Ref<StrategyName>, localStorageDataUpdate?: boolean) => {
  const form = $form[strategyName.value];

  const values = computed(
    () =>
      Object.keys(form).reduce(
        (acc, key) => ({ ...acc, [key]: fixValue(form[key].value.value) }),
        {},
      ) as FormValue,
  );

  const localStorageData = localStorage.getItem(strategyName.value);

  if (localStorageData && localStorageDataUpdate) {
    const parsedLocalStorage = JSON.parse(localStorageData);

    Object.keys(form).forEach((val) => {
      form[val].value.value = parsedLocalStorage[val];
    });
  }

  return { fields: form, values };
};
