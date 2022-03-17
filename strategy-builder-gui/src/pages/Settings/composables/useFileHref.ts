import { StrategyName } from 'src/stores/strategies';
import { computed, Ref } from 'vue';

import { $fileMap } from '../stores/form';
import { OrderType } from '../stores/form.types';
import { useForm } from './useForm';

export const useFileHref = (strategyName: Ref<StrategyName>) => {
  const { values } = useForm(strategyName);
  return computed(() => {
    const valuesObj = Object.keys($fileMap[strategyName.value]).reduce((acc, key) => {
      const fieldName = $fileMap[strategyName.value][key];
      let fieldValue: string | number | boolean | string[] =
        values.value[key] === undefined ? '' : values.value[key];

      if (fieldName === 'orders') {
        const ordersArr: OrderType[] = JSON.parse(JSON.stringify(fieldValue));
        const ordersFormatArr: string[] = [];
        ordersArr.forEach((val, index) => {
          ordersFormatArr.push(
            `order_${index + 1}: [${[
              String(val.value),
              String(val.orderAmount.value),
              String(val.orderLevelParam.value),
            ]}]`
              .replace(/,/g, '-')
              .replace(/(\[)|(\])/g, '='),
          );
        });
        fieldValue = ordersFormatArr;
      }
      return {
        ...acc,
        [fieldName]: fieldValue,
      };
    }, {});
    let iterator = 0;
    return `data:text/plain,${JSON.stringify(valuesObj, null, 1)
      .replace(/[{},"]/g, '')
      .replace(/-/g, ', ')
      .replace(/(\[)|(\])/g, '')
      .replace(/=/g, () => {
        iterator += 1;
        if (iterator % 2 === 0) {
          return ']';
        }
        return '[';
      })}`;
  });
};
