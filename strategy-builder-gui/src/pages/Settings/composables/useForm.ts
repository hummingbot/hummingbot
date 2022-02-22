import { StrategyName } from 'src/composables/useStrategies';
import { computed } from 'vue';

import { $form } from '../stores/form';

export { BtnToggleType } from '../stores/form.types';

export const useForm = (strategyName: StrategyName) => {
  const values = computed(() =>
    Object.keys($form[strategyName]).reduce(
      (acc, key) => ({ ...acc, [key]: $form[strategyName][key].value.value }),
      {},
    ),
  );

  return { fields: $form[strategyName], values };
};
