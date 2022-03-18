import { StrategyName } from 'src/composables/useStrategies';
import { Ref } from 'vue';

import { $form } from '../stores/form';
import { Order } from '../stores/form.types';
import { defaultOrder } from '../stores/pureMMForm';

export { BtnToggleType } from '../stores/form.types';

export const useOrders = (strategyName: Ref<StrategyName>) => {
  const orders = $form[strategyName.value].orders.value as Ref<Order[]>;

  const add = () => {
    orders.value.push(JSON.parse(JSON.stringify(defaultOrder)));
  };

  const removeLast = () => {
    orders.value.pop();
  };

  return { value: orders, add, removeLast };
};
