import { StrategyName } from 'src/composables/useStrategies';
import { computed } from 'vue';

import { $settingsForm } from '../stores/form';

export { BtnToggleType } from '../stores/form.types';

export const useForm = (form: StrategyName) => {
  const values = computed(() =>
    Object.keys($settingsForm[form]).reduce(
      (acc, key) => ({ ...acc, [key]: $settingsForm[form][key].value.value }),
      {},
    ),
  );

  return { settingsForm: $settingsForm[form], values, StrategyName };
};
