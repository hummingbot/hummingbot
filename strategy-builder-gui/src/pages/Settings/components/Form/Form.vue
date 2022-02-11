<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders">
    <div class="text-white text-h4 q-mb-xl">Settings</div>
    <q-form class="q-gutter-md" @submit="onSubmit">
      <Field title="Exchange">
        <Select
          :model-value="selectAgrs.exchange.model.value"
          :label-text="selectAgrs.exchange.labelText"
          :options="selectAgrs.exchange.options"
          :name="selectAgrs.exchange.name"
          :on-change="onChangeSelect"
        />
      </Field>
      <Field title="Market">
        <Select
          :model-value="selectAgrs.market.model.value"
          :label-text="selectAgrs.market.labelText"
          :options="selectAgrs.market.options"
          :name="selectAgrs.market.name"
          :on-change="onChangeSelect"
        />
      </Field>
      <Field title="Bid spread">
        <Counter />
      </Field>
      <q-btn label="Submit" type="submit" color="primary" />
    </q-form>
  </div>
</template>

<script lang="ts">
import { defineComponent, Ref, ref } from 'vue';

import Counter from './Counter.vue';
import Field from './Field.vue';
import Select from './Select.vue';

type SelectAgrs = {
  [key: string]: {
    model: Ref<unknown>;
    options: string[];
    labelText: string;
    name: string;
  };
};

type SubmitResult = {
  [key: string]: unknown;
};

export default defineComponent({
  components: { Field, Select, Counter },
  setup() {
    const selectAgrs: SelectAgrs = {
      exchange: {
        model: ref(''),
        options: ['1', '2', '3', '4', '5'],
        labelText: 'Select exchange',
        name: 'exchange',
      },
      market: {
        model: ref(''),
        options: ['1', '2', '3', '4', '5'],
        labelText: 'Select market',
        name: 'market',
      },
    };

    const onChangeSelect = (value: string, name: string) => {
      if (value !== selectAgrs[name].model.value) {
        selectAgrs[name].model.value = value;
      }
    };

    const onSubmit = () => {
      const result: SubmitResult = {};
      Object.keys(selectAgrs).forEach((key) => {
        result[key] = selectAgrs[key].model.value;
      });

      // eslint-disable-next-line no-console
      console.log(result);
    };

    return { onSubmit, selectAgrs, onChangeSelect };
  },
});
</script>
