<template>
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
  <div v-if="formType === FormType.Basic" class="q-gutter-md">
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
  </div>
  <div v-if="formType === FormType.Advanced" class="q-gutter-md">
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
      <Counter
        v-model="inventoryTargetBase.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...inventoryTargetBase.properties }"
      />
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
        v-model="hangingOrdersCancel.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...hangingOrdersCancel.properties }"
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
        v-model="orderRefreshTolerance.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...orderRefreshTolerance.properties }"
      />
    </Field>
    <Field title="Price ceiling">
      <Input
        v-model="priceCelling.value.value"
        :type="InputType.Number"
        v-bind="{ ...priceCelling.properties }"
      />
    </Field>
    <Field title="Price floor">
      <Input
        v-model="priceFloor.value.value"
        :type="InputType.Number"
        v-bind="{ ...priceFloor.properties }"
      />
    </Field>
    <Field title="Order optimization">
      <q-toggle v-model="orderOptimization.value.value" color="main-green-1" />
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
        v-model="priceSourceCustomApi.value.value"
        :type="InputType.Number"
        v-bind="{ ...priceSourceCustomApi.properties }"
        class="col-6"
      />
    </Field>
    <Field title="Custom API update interval">
      <Counter
        v-model="customApiUpdateInterval.value.value"
        :type="CounterType.Seconds"
        v-bind="{ ...customApiUpdateInterval.properties }"
      />
    </Field>
    <Field class="q-gutter-xs justify-center">
      <Order
        v-for="(order, index) in displayOrders.value"
        :key="index"
        :title="`Order ${index + 1}`"
        hint="Order hint"
      >
        <template #toggle>
          <q-btn-toggle
            v-model="order.value"
            class="flex justify-between full-width"
            unelevated
            :ripple="false"
            toggle-color="mono-grey-2"
            text-color="mono-grey-3"
            :options="[
              { label: 'sell', value: BtnToggleType.Sell },
              { label: 'buy', value: BtnToggleType.Buy },
            ]"
          />
        </template>
        <template #counters>
          <Counter
            v-model="order.orderAmount.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order.orderAmount.properties }"
          />
          <Counter
            v-model="order.orderLevelParam.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order.orderLevelParam.properties }"
          />
        </template>
      </Order>
    </Field>
    <Field title="Max. order age">
      <Counter
        v-model="maxOrderAge.value.value"
        :type="CounterType.Seconds"
        v-bind="{ ...maxOrderAge.properties }"
      />
    </Field>
  </div>
</template>
<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { computed, defineComponent, ref, watch } from 'vue';

import Counter, { CounterType } from '../components/Counter.vue';
import Field from '../components/Field.vue';
import Input, { InputType } from '../components/Input.vue';
import Order from '../components/Order.vue';
import Select from '../components/Select/Index.vue';
import { BtnToggleType, useForm } from '../composables/useForm';
import { useOrders } from '../composables/useOrders';

enum FormType {
  Basic,
  Advanced,
}

export default defineComponent({
  name: 'PureMMForm',
  components: { Field, Select, Counter, Input, Order },

  emits: ['update:formType'],

  setup() {
    const strategyName = ref(StrategyName.PureMarketMaking);
    const { fields } = useForm(strategyName);
    const formType = ref(FormType.Basic);
    const { computedOrders, addOrder, removeLastOrder } = useOrders(strategyName);

    const displayOrders = computed(() => computedOrders);

    watch(fields.orderLevels.value, (value, prev) => {
      if (value > prev) {
        addOrder();
      } else {
        removeLastOrder();
      }
    });

    return {
      ...fields,
      CounterType,
      InputType,
      formType,
      FormType,
      BtnToggleType,
      displayOrders,
    };
  },
});
</script>
