<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders q-mt-md full-width">
    <div class="text-white text-h4 q-mb-xl">Settings</div>
    <div class="row q-gutter-md q-mb-lg">
      <q-btn
        v-model="formType"
        flat
        rounded
        :ripple="false"
        class="text-capitalize"
        :class="formType === FormType.Basic ? 'text-white bg-mono-grey-2' : 'bg-none'"
        @click="formType = FormType.Basic"
      >
        Basic
      </q-btn>
      <q-btn
        v-model="formType"
        rounded
        flat
        :ripple="false"
        class="text-capitalize"
        :class="formType === FormType.Advanced ? 'text-white bg-mono-grey-2' : 'bg-none'"
        @click="formType = FormType.Advanced"
      >
        Advanced
      </q-btn>
    </div>
    <q-form v-if="formType === FormType.Basic" class="q-gutter-md" @submit="handleSubmit">
      <Field title="Exchange">
        <Select v-model="exchange.value.value" v-bind="{ ...exchange.properties }" />
      </Field>
      <Field title="Market">
        <Select v-model="market.value.value" v-bind="{ ...market.properties }" />
      </Field>
      <Field
        title="Bid spread"
        hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
      >
        <Counter
          v-model="bidSpread.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...bidSpread.properties }"
        />
      </Field>
      <Field
        title="Ask spread"
        hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
      >
        <Counter
          v-model="askSpread.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...askSpread.properties }"
        />
      </Field>
      <Field
        title="Order refresh time"
        hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
      >
        <Counter
          v-model="orderRefreshTime.value.value"
          :type="CounterType.Seconds"
          v-bind="{ ...orderRefreshTime.properties }"
        />
      </Field>
      <Field
        title="Order amount"
        hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
      >
        <Input
          v-model="orderAmount.value.value"
          :type="InputType.Number"
          v-bind="{ ...orderAmount.properties }"
        />
      </Field>
      <Field
        title="Ping pong"
        hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
      >
        <q-toggle v-model="pingPong.value.value" color="main-green-1" />
      </Field>
    </q-form>
    <q-form v-if="formType === FormType.Advanced" class="q-gutter-md" @submit="handleSubmit">
      <Field title="Order levels">
        <Counter
          v-model="orderLevels.value.value"
          :type="CounterType.CountInt"
          v-bind="{ ...orderLevels.properties }"
        />
      </Field>
      <Field title="Order level amount">
        <Counter
          v-model="orderLevelAmount.value.value"
          :type="CounterType.CountInt"
          v-bind="{ ...orderLevelAmount.properties }"
        />
      </Field>
      <Field title="Order level spread">
        <Counter
          v-model="orderLevelSpread.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...orderLevelSpread.properties }"
        />
      </Field>
      <Field title="Inventory skew">
        <q-toggle v-model="inventorySkew.value.value" color="main-green-1" />
      </Field>
      <Field title="Inventory target base">
        <div class="row q-col-gutter-md">
          <Counter
            v-model="inventoryTargetBaseCounter.value.value"
            :type="CounterType.Percentage"
            v-bind="{ ...inventoryTargetBaseCounter.properties }"
          />
          <q-toggle v-model="inventoryTargetBaseToggle.value.value" color="main-green-1" />
        </div>
      </Field>
      <Field title="Inventory range multiplier">
        <Counter
          v-model="inventoryRangeMultiplier.value.value"
          :type="CounterType.FloatCount"
          v-bind="{ ...inventoryRangeMultiplier.properties }"
        />
      </Field>
      <Field title="Inventory price">
        <Input
          v-model="inventoryPrice.value.value"
          :type="InputType.Number"
          v-bind="{ ...inventoryPrice.properties }"
        />
      </Field>
      <Field title="Filled order delay">
        <Counter
          v-model="filledOrderDelay.value.value"
          :type="CounterType.Seconds"
          v-bind="{ ...filledOrderDelay.properties }"
        />
      </Field>
      <Field title="Hanging orders">
        <q-toggle v-model="hangingOrders.value.value" color="main-green-1" />
      </Field>
      <Field title="Hanging order cancel percentage">
        <Counter
          v-model="hangingOrderCancel.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...hangingOrderCancel.properties }"
        />
      </Field>
      <Field title="Minimum spread">
        <Counter
          v-model="minimumSpread.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...minimumSpread.properties }"
        />
      </Field>
      <Field title="Order refresh tollerance">
        <Counter
          v-model="orderRefreshTollerance.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...orderRefreshTollerance.properties }"
        />
      </Field>
      <Field title="Price ceiling">
        <Input
          v-model="priceCeiling.value.value"
          :type="InputType.Number"
          v-bind="{ ...priceCeiling.properties }"
        />
      </Field>
      <Field title="Price floor">
        <Input
          v-model="priceFloor.value.value"
          :type="InputType.Number"
          v-bind="{ ...priceFloor.properties }"
        />
      </Field>
      <Field title="Order optimisation">
        <q-toggle v-model="orderOptimisation.value.value" color="main-green-1" />
      </Field>
      <Field title="Ask order optimization depth">
        <Input
          v-model="askOrderOptimizationDepth.value.value"
          :type="InputType.Number"
          v-bind="{ ...askOrderOptimizationDepth.properties }"
        />
      </Field>
      <Field title="Bid order optimization depth">
        <Input
          v-model="bidOrderOptimizationDepth.value.value"
          :type="InputType.Number"
          v-bind="{ ...bidOrderOptimizationDepth.properties }"
        />
      </Field>
      <Field title="Add transaction costs">
        <q-toggle v-model="addTransactionCosts.value.value" color="main-green-1" />
      </Field>
      <Field title="Price source">
        <Select v-model="priceSource.value.value" v-bind="{ ...priceSource.properties }" />
      </Field>
      <Field title="Price type">
        <Select v-model="priceType.value.value" v-bind="{ ...priceType.properties }" />
      </Field>
      <Field title="Price source exchange">
        <Select
          v-model="priceSourceExchange.value.value"
          v-bind="{ ...priceSourceExchange.properties }"
        />
      </Field>
      <Field title="Price source market">
        <Select
          v-model="priceSourceMarket.value.value"
          v-bind="{ ...priceSourceMarket.properties }"
        />
      </Field>
      <Field title="Take if crossed">
        <q-toggle v-model="takeIfCrossed.value.value" color="main-green-1" />
      </Field>
      <Field title="Price source custom API">
        <Input
          v-model="priceSourceCustomAPI.value.value"
          :type="InputType.Number"
          v-bind="{ ...priceSourceCustomAPI.properties }"
          class="col-6"
        />
      </Field>
      <Field class="q-gutter-md">
        <Order v-model="order1.value.value" v-bind="{ ...order1.properties }">
          <Counter
            v-model="order1FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order1FirstCounter.properties }"
          />
          <Counter
            v-model="order1SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order1SecondCounter.properties }"
          />
        </Order>
        <Order v-model="order2.value.value" v-bind="{ ...order2.properties }">
          <Counter
            v-model="order2FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order2FirstCounter.properties }"
          />
          <Counter
            v-model="order2SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order2SecondCounter.properties }"
          />
        </Order>
        <Order v-model="order3.value.value" v-bind="{ ...order3.properties }">
          <Counter
            v-model="order3FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order3FirstCounter.properties }"
          />
          <Counter
            v-model="order3SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order3SecondCounter.properties }"
          />
        </Order>
        <Order v-model="order4.value.value" v-bind="{ ...order4.properties }">
          <Counter
            v-model="order4FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order4FirstCounter.properties }"
          />
          <Counter
            v-model="order4SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order4SecondCounter.properties }"
          />
        </Order>
      </Field>
      <Field title="Max. order age">
        <Counter
          v-model="maxOrderAge.value.value"
          :type="CounterType.Seconds"
          v-bind="{ ...maxOrderAge.properties }"
        />
      </Field>
      <q-btn label="Submit" type="submit" color="primary" />
    </q-form>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';

import { useSettingsForm } from '../composables/useSettingsForm';
import Counter, { CounterType } from './Counter.vue';
import Field from './Field/Index.vue';
import Input, { InputType } from './Input.vue';
import Order from './Order.vue';
import Select from './Select/Index.vue';

enum FormType {
  Basic,
  Advanced,
}

export default defineComponent({
  components: { Field, Select, Counter, Input, Order },
  emits: ['update:formType'],

  setup() {
    const { settingsForm, values } = useSettingsForm();
    const formType = ref(FormType.Basic);

    const handleSubmit = () => {
      // eslint-disable-next-line no-console
      console.log(values.value);
    };

    return {
      handleSubmit,
      ...settingsForm,
      CounterType,
      InputType,
      formType,
      FormType,
    };
  },
});
</script>
