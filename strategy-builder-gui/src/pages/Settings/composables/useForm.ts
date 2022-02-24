import { StrategyName } from 'src/composables/useStrategies';
import { computed, Ref } from 'vue';

import { $form } from '../stores/form';

export { BtnToggleType } from '../stores/form.types';

export const useForm = (strategyName: Ref<StrategyName>) => {
  const values = computed(() =>
    Object.keys($form[strategyName.value]).reduce(
      (acc, key) => ({ ...acc, [key]: $form[strategyName.value][key].value.value }),
      {},
    ),
  );

  return { fields: $form[strategyName.value], values };
};
