import { StrategyName } from 'src/stores/strategies';
import { computed, Ref } from 'vue';

import { $fileMap } from '../stores/form';
import { useForm } from './useForm';

export const useFileHref = (strategyName: Ref<StrategyName>) => {
  const { values } = useForm(strategyName);
  return computed(() => {
    const valuesObj = Object.keys($fileMap).reduce(
      (acc, key) => ({
        ...acc,
        [Object.getOwnPropertyDescriptor($fileMap[strategyName.value], key)?.value]: `${
          Object.getOwnPropertyDescriptor(values.value, key)?.value ?? ''
        }`,
      }),
      {},
    );

    return `data:text/plain,${JSON.stringify(valuesObj, null, 1).replace(/[{}",]/g, '')}`;
  });
};
