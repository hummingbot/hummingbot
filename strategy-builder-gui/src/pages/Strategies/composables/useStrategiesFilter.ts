import { computed, Ref } from 'vue';

import { $strategies, StrategyCategory } from '../../../stores/strategies';

export const useStrategiesFilter = (category: Ref<StrategyCategory>) => {
  const strategies = computed(() =>
    $strategies.value
      .sort((a, b) => a.place - b.place)
      .filter((val) => category.value === StrategyCategory.All || category.value === val.category),
  );
  const categories: string[] = Object.values(StrategyCategory);

  return { strategies, categories };
};
