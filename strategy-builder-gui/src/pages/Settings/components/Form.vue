<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders q-mt-md full-width">
    <div class="text-white text-h4 q-mb-xl">Settings</div>
    <q-form class="q-gutter-md" @submit="handleSubmit">
      <Field title="Exchange">
        <Select v-model="exchange.value.value" v-bind="{ ...exchange.properties }" />
      </Field>
      <Field title="Market">
        <Select v-model="market.value.value" v-bind="{ ...market.properties }" />
      </Field>
      <Field title="Bid spread">
        <Counter
          v-model="bidSpread.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...bidSpread.properties }"
        />
      </Field>
      <Field title="Ask spread">
        <Counter
          v-model="askSpread.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...askSpread.properties }"
        />
      </Field>
      <Field title="Order refresh time">
        <Counter
          v-model="orderRefreshTime.value.value"
          :type="CounterType.Seconds"
          v-bind="{ ...orderRefreshTime.properties }"
        />
      </Field>
      <Field title="Order amount">
        <Input
          v-model="orderAmount.value.value"
          :type="InputType.Number"
          v-bind="{ ...orderAmount.properties }"
        />
      </Field>
      <Field title="Ping pong">
        <q-toggle v-model="pingPong.value.value" color="main-green-1" />
      </Field>
      <q-btn label="Submit" type="submit" color="main-green-1" />
    </q-form>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import { useSettingsForm } from '../composables/useSettingsForm';
import Counter, { CounterType } from './Counter.vue';
import Field from './Field.vue';
import Input, { InputType } from './Input.vue';
import Select from './Select/Index.vue';

export default defineComponent({
  components: { Field, Select, Counter, Input },

  setup() {
    const { settingsForm, values } = useSettingsForm();

    const handleSubmit = () => {
      // eslint-disable-next-line no-console
      console.log(values.value);
    };

    return {
      handleSubmit,
      ...settingsForm,
      CounterType,
      InputType,
    };
  },
});
</script>
