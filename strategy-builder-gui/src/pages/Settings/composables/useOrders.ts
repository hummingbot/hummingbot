import { StrategyName } from 'src/composables/useStrategies';
import { Ref } from 'vue';

import { $form } from '../stores/form';
import { Order } from '../stores/form.types';
import { defaultOrder } from '../stores/pureMMForm';

export { BtnToggleType } from '../stores/form.types';

export const useOrders = (strategyName: Ref<StrategyName>) => {
  const orders = $form[strategyName.value].orders.value as Ref<Order[]>;

  const update = (ordersLevelAmount: number | string) => {
    const parsedValue = parseInt(String(ordersLevelAmount), 10);
    const ordersLength = orders.value.length;

    if (parsedValue !== ordersLength && !Number.isNaN(parsedValue)) {
      if (ordersLength > parsedValue) {
        orders.value.splice(parsedValue, ordersLength - parsedValue);
      } else {
        for (let i = 0; i < parsedValue - ordersLength; i += 1) {
          orders.value.push(JSON.parse(JSON.stringify(defaultOrder)));
        }
      }
    }
  };

  return { value: orders, update };
};
