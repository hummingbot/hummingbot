import { StrategyName } from 'src/composables/useStrategies';
import { Ref, ref } from 'vue';

import { $form } from '../stores/form';
import { Orders } from '../stores/form.types';
import { defaultOrder } from '../stores/pureMMForm';

export { BtnToggleType } from '../stores/form.types';

export const useOrders = (strategyName: Ref<StrategyName>) => {
  const { list } = $form[strategyName.value].orders as Orders;
  const computedOrders = ref(list);

  const orderLevels = $form[strategyName.value].orderLevels.value.value;

  const addOrder = () => {
    computedOrders.value.push(JSON.parse(JSON.stringify(defaultOrder)));
  };

  const removeLastOrder = () => {
    computedOrders.value.pop();
  };

  for (let i = 0; i < orderLevels; i += 1) {
    addOrder();
  }

  return { computedOrders, addOrder, removeLastOrder };
};
