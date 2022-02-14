<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders q-mt-md full-width">
    <div class="text-white text-h4 q-mb-xl">Settings</div>
    <q-form class="q-gutter-md" @submit="onSubmit">
      <Field title="Exchange">
        <Select
          v-bind="{ ...selects.exchange.value }"
          @update:modelValue="selects.exchange.value.modelValue = $event"
        />
      </Field>
      <Field title="Market">
        <Select
          v-bind="{ ...selects.market.value }"
          @update:modelValue="selects.market.value.modelValue = $event"
        />
      </Field>
      <Field title="Bid spread">
        <Counter
          :type="CounterType.Percentage"
          v-bind="{ ...counters.bidSpread.value }"
          @update:modelValue="counters.bidSpread.value.modelValue += $event"
        />
      </Field>
      <Field title="Ask spread">
        <Counter
          :type="CounterType.Percentage"
          v-bind="{ ...counters.askSpread.value }"
          @update:modelValue="counters.askSpread.value.modelValue += $event"
        />
      </Field>
      <Field title="Order refresh time">
        <Counter
          :type="CounterType.Seconds"
          v-bind="{ ...counters.orderRefreshTime.value }"
          @update:modelValue="counters.orderRefreshTime.value.modelValue += $event"
        />
      </Field>
      <Field title="Order amount">
        <Input
          :type="InputType.Number"
          v-bind="{ ...inputs.orderAmount.value }"
          @update:modelValue="inputs.orderAmount.value.modelValue = $event"
        />
      </Field>
      <Field title="Ping pong">
        <q-toggle
          :model-value="toggles.pingPong.value.modelValue"
          color="main-green-1"
          @update:model-value="(value) => (toggles.pingPong.value.modelValue = value)"
        />
      </Field>
      <q-btn label="Submit" type="submit" color="main-green-1" />
    </q-form>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import { useSettingsForm } from '../../composables/useSettingsForm';
import Counter, { CounterType } from './Counter.vue';
import Field from './Field.vue';
import Input, { InputType } from './Input.vue';
import Select from './Select.vue';

export default defineComponent({
  components: { Field, Select, Counter, Input },

  setup() {
    const { settingsForm, submitValue } = useSettingsForm();

    const onSubmit = () => {
      // eslint-disable-next-line no-console
      console.log(submitValue.value);
    };

    return {
      onSubmit,
      ...settingsForm,
      CounterType,
      InputType,
    };
  },
});
</script>
