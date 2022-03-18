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
      <Input
        v-model="bidSpread.value.value"
        :type="InputType.Number"
        v-bind="{ ...bidSpread.properties }"
        class="col-2"
      />
    </Field>
    <Field
      title="Ask spread"
      hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    >
      <Input
        v-model="askSpread.value.value"
        :type="InputType.Number"
        v-bind="{ ...askSpread.properties }"
        class="col-2"
      />
    </Field>
    <Field
      title="Order refresh time"
      hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    >
      <Input
        v-model="orderRefreshTime.value.value"
        :type="InputType.Number"
        v-bind="{ ...orderRefreshTime.properties }"
        class="col-2"
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
      <Input
        v-model="orderLevels.value.value"
        :type="InputType.Number"
        v-bind="{ ...orderLevels.properties }"
        class="col-2"
      />
    </Field>
    <Field title="Order level amount">
      <Input
        v-model="orderLevelAmount.value.value"
        :type="InputType.Number"
        v-bind="{ ...orderLevelAmount.properties }"
        class="col-2"
      />
    </Field>
    <Field title="Order level spread">
      <Input
        v-model="orderLevelSpread.value.value"
        :type="InputType.Number"
        v-bind="{ ...orderLevelSpread.properties }"
        class="col-2"
      />
    </Field>
    <Field title="Inventory skew">
      <q-toggle v-model="inventorySkew.value.value" color="main-green-1" />
    </Field>
    <Field title="Inventory target base">
      <Input
        v-model="inventoryTargetBase.value.value"
        :type="InputType.Number"
        v-bind="{ ...inventoryTargetBase.properties }"
        class="col-2"
      />
    </Field>
    <Field title="Inventory range multiplier">
      <Input
        v-model="inventoryRangeMultiplier.value.value"
        :type="InputType.Number"
        v-bind="{ ...inventoryRangeMultiplier.properties }"
        class="col-2"
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
      <Input
        v-model="filledOrderDelay.value.value"
        :type="InputType.Number"
        v-bind="{ ...filledOrderDelay.properties }"
        class="col-2"
      />
    </Field>
    <Field title="Hanging orders">
      <q-toggle v-model="hangingOrders.value.value" color="main-green-1" />
    </Field>
    <Field title="Hanging order cancel percentage">
      <Input
        v-model="hangingOrdersCancel.value.value"
        :type="InputType.Number"
        v-bind="{ ...hangingOrdersCancel.properties }"
        class="col-2"
      />
    </Field>
    <Field title="Minimum spread">
      <Input
        v-model="minimumSpread.value.value"
        :type="InputType.Number"
        v-bind="{ ...minimumSpread.properties }"
        class="col-2"
      />
    </Field>
    <Field title="Order refresh tollerance">
      <Input
        v-model="orderRefreshTolerance.value.value"
        :type="InputType.Number"
        v-bind="{ ...orderRefreshTolerance.properties }"
        class="col-2"
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
        :type="InputType.Text"
        v-bind="{ ...priceSourceCustomApi.properties }"
        class="col-6"
      />
    </Field>
    <Field title="Custom API update interval">
      <Input
        v-model="customApiUpdateInterval.value.value"
        :type="InputType.Number"
        v-bind="{ ...customApiUpdateInterval.properties }"
        class="col-2"
      />
    </Field>
    <Field class="q-gutter-y-md" :orders-field="true">
      <Order
        v-for="(order, index) in orders"
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
          <Input
            v-model="order.orderAmount.value"
            :type="InputType.Number"
            v-bind="{ ...order.orderAmount.properties }"
          />
          <Input
            v-model="order.orderLevelParam.value"
            :type="InputType.Number"
            v-bind="{ ...order.orderLevelParam.properties }"
          />
        </template>
      </Order>
    </Field>
    <Field title="Max. order age">
      <Input
        v-model="maxOrderAge.value.value"
        :type="InputType.Number"
        v-bind="{ ...maxOrderAge.properties }"
        class="col-2"
      />
    </Field>
  </div>
</template>
<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent, ref, watch } from 'vue';

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
  components: { Field, Select, Input, Order },

  emits: ['update:formType'],

  setup() {
    const strategyName = ref(StrategyName.PureMarketMaking);
    const { fields, init } = useForm(strategyName);
    const formType = ref(FormType.Basic);
    const orders = useOrders(strategyName);

    init();

    watch(fields.orderLevels.value, (value) => {
      orders.update(String(value));
    });

    return {
      ...fields,
      InputType,
      formType,
      FormType,
      BtnToggleType,
      orders: orders.value,
    };
  },
});
</script>
