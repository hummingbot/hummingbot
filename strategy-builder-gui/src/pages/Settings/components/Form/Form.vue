<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders">
    <div class="text-white text-h4 q-mb-xl">Settings</div>
    <q-form class="q-gutter-md" @submit="onSubmit">
      <Field title="Exchange">
        <Select
          :v-model="selects.exchange.model"
          :model-value="selects.exchange.model.value"
          :label-text="selects.exchange.labelText"
          :options="selects.exchange.options"
          :name="selects.exchange.name"
          :on-change="onChangeSelect"
        />
      </Field>
      <Field title="Market">
        <Select
          :model-value="selects.market.model.value"
          :label-text="selects.market.labelText"
          :options="selects.market.options"
          :name="selects.market.name"
          :on-change="onChangeSelect"
        />
      </Field>
      <Field title="Bid spread">
        <Counter
          :type="counters.bidSpread.type"
          :name="counters.bidSpread.name"
          :counter-value="counters.bidSpread.model.value"
          :max="counters.bidSpread.max"
          :min="counters.bidSpread.min"
          :step-value="counters.bidSpread.stepValue"
          :on-click="onClickCounterBtn"
        />
      </Field>
      <Field title="Ask spread">
        <Counter
          :type="counters.askSread.type"
          :name="counters.askSread.name"
          :counter-value="counters.askSread.model.value"
          :max="counters.askSread.max"
          :min="counters.askSread.min"
          :step-value="counters.askSread.stepValue"
          :on-click="onClickCounterBtn"
        />
      </Field>
      <Field title="Order refresh time">
        <Counter
          :type="counters.orderRefreshTime.type"
          :name="counters.orderRefreshTime.name"
          :counter-value="counters.orderRefreshTime.model.value"
          :max="counters.orderRefreshTime.max"
          :min="counters.orderRefreshTime.min"
          :step-value="counters.orderRefreshTime.stepValue"
          :on-click="onClickCounterBtn"
        />
      </Field>
      <q-btn label="Submit" type="submit" color="primary" />
    </q-form>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Counter from './Counter.vue';
import Field from './Field.vue';
import Select from './Select.vue';
import { counters } from './stores/counters';
import { selects } from './stores/selects';

type SubmitResult = {
  [key: string]: unknown;
};

export default defineComponent({
  components: { Field, Select, Counter },
  setup() {
    const onClickCounterBtn = (value: number, name: string) => {
      counters[name].model.value += value;
    };

    const onChangeSelect = (value: string, name: string) => {
      if (value !== selects[name].model.value) {
        selects[name].model.value = value;
      }
    };

    const onSubmit = () => {
      const result: SubmitResult = {};
      const formObject = Object.assign(selects, counters);

      Object.keys(formObject).forEach((key) => {
        result[key] = formObject[key].model.value;
      });

      // eslint-disable-next-line no-console
      console.log(result);
    };

    return { onSubmit, selects, onChangeSelect, counters, onClickCounterBtn };
  },
});
</script>
