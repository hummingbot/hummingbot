import { StrategyName } from 'src/stores/strategies';
import { computed, Ref } from 'vue';

import { $fileMap } from '../stores/form';
import { useForm } from './useForm';

export const useFileHref = (strategyName: Ref<StrategyName>) => {
  const { values } = useForm(strategyName);
  return computed(() => {
    const valuesObj = Object.keys($fileMap[strategyName.value]).reduce((acc, key) => {
      const fieldName = $fileMap[strategyName.value][key];
      const fieldValue = values.value[key] === undefined ? '' : values.value[key];
      return {
        ...acc,
        [fieldName]: fieldValue,
      };
    }, {});

    return `data:text/plain,${JSON.stringify(valuesObj, null, 1).replace(/[{}",]/g, '')}`;
  });
};
