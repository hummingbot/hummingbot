import { $strategies, StrategyCategory } from 'src/stores/strategies';
import { computed, Ref } from 'vue';

export { StrategyName } from 'src/stores/strategies';

export const useStrategiesByCategory = (category: Ref<StrategyCategory>) => {
  const strategies = computed(() =>
    $strategies.value
      .sort((a, b) => a.place - b.place)
      .filter((val) => category.value === StrategyCategory.All || category.value === val.category),
  );

  return { strategies };
};
