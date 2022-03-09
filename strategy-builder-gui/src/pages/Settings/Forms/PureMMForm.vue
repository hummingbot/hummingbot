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
        v-model="bid_spread.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...bid_spread.properties }"
      />
    </Field>
    <Field
      title="Ask spread"
      hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    >
      <Counter
        v-model="ask_spread.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...ask_spread.properties }"
      />
    </Field>
    <Field
      title="Order refresh time"
      hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    >
      <Counter
        v-model="order_refresh_time.value.value"
        :type="CounterType.Seconds"
        v-bind="{ ...order_refresh_time.properties }"
      />
    </Field>
    <Field
      title="Order amount"
      hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    >
      <Input
        v-model="order_amount.value.value"
        :type="InputType.Number"
        v-bind="{ ...order_amount.properties }"
      />
    </Field>
    <Field
      title="Ping pong"
      hint="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    >
      <q-toggle v-model="ping_pong_enabled.value.value" color="main-green-1" />
    </Field>
  </div>
  <div v-if="formType === FormType.Advanced" class="q-gutter-md">
    <Field title="Order levels">
      <Counter
        v-model="order_levels.value.value"
        :type="CounterType.CountInt"
        v-bind="{ ...order_levels.properties }"
      />
    </Field>
    <Field title="Order level amount">
      <Counter
        v-model="order_level_amount.value.value"
        :type="CounterType.CountInt"
        v-bind="{ ...order_level_amount.properties }"
      />
    </Field>
    <Field title="Order level spread">
      <Counter
        v-model="order_levelspread.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...order_levelspread.properties }"
      />
    </Field>
    <Field title="Inventory skew">
      <q-toggle v-model="inventory_skew_enabled.value.value" color="main-green-1" />
    </Field>
    <Field title="Inventory target base">
      <div class="row q-col-gutter-md">
        <Counter
          v-model="inventory_target_base_pctCounter.value.value"
          :type="CounterType.Percentage"
          v-bind="{ ...inventory_target_base_pctCounter.properties }"
        />
        <q-toggle v-model="inventory_target_base_pctToggle.value.value" color="main-green-1" />
      </div>
    </Field>
    <Field title="Inventory range multiplier">
      <Counter
        v-model="inventory_range_multiplier.value.value"
        :type="CounterType.FloatCount"
        v-bind="{ ...inventory_range_multiplier.properties }"
      />
    </Field>
    <Field title="Inventory price">
      <Input
        v-model="inventory_price.value.value"
        :type="InputType.Number"
        v-bind="{ ...inventory_price.properties }"
      />
    </Field>
    <Field title="Filled order delay">
      <Counter
        v-model="filled_order_delay.value.value"
        :type="CounterType.Seconds"
        v-bind="{ ...filled_order_delay.properties }"
      />
    </Field>
    <Field title="Hanging orders">
      <q-toggle v-model="hanging_orders_enabled.value.value" color="main-green-1" />
    </Field>
    <Field title="Hanging order cancel percentage">
      <Counter
        v-model="hanging_orders_cancel_pct.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...hanging_orders_cancel_pct.properties }"
      />
    </Field>
    <Field title="Minimum spread">
      <Counter
        v-model="minimum_spread.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...minimum_spread.properties }"
      />
    </Field>
    <Field title="Order refresh tollerance">
      <Counter
        v-model="order_refresh_tolerance_pct.value.value"
        :type="CounterType.Percentage"
        v-bind="{ ...order_refresh_tolerance_pct.properties }"
      />
    </Field>
    <Field title="Price ceiling">
      <Input
        v-model="price_ceiling.value.value"
        :type="InputType.Number"
        v-bind="{ ...price_ceiling.properties }"
      />
    </Field>
    <Field title="Price floor">
      <Input
        v-model="price_floor.value.value"
        :type="InputType.Number"
        v-bind="{ ...price_floor.properties }"
      />
    </Field>
    <Field title="Order optimisation">
      <q-toggle v-model="orderOptimisation.value.value" color="main-green-1" />
    </Field>
    <Field title="Ask order optimization depth">
      <Input
        v-model="ask_order_optimization_depth.value.value"
        :type="InputType.Number"
        v-bind="{ ...ask_order_optimization_depth.properties }"
      />
    </Field>
    <Field title="Bid order optimization depth">
      <Input
        v-model="bid_order_optimization_depth.value.value"
        :type="InputType.Number"
        v-bind="{ ...bid_order_optimization_depth.properties }"
      />
    </Field>
    <Field title="Add transaction costs">
      <q-toggle v-model="add_transaction_costs.value.value" color="main-green-1" />
    </Field>
    <Field title="Price source">
      <Select v-model="price_source.value.value" v-bind="{ ...price_source.properties }" />
    </Field>
    <Field title="Price type">
      <Select v-model="price_type.value.value" v-bind="{ ...price_type.properties }" />
    </Field>
    <Field title="Price source exchange">
      <Select
        v-model="price_source_exchange.value.value"
        v-bind="{ ...price_source_exchange.properties }"
      />
    </Field>
    <Field title="Price source market">
      <Select
        v-model="price_source_market.value.value"
        v-bind="{ ...price_source_market.properties }"
      />
    </Field>
    <Field title="Take if crossed">
      <q-toggle v-model="take_if_crossed.value.value" color="main-green-1" />
    </Field>
    <Field title="Price source custom API">
      <Input
        v-model="price_source_custom_api.value.value"
        :type="InputType.Number"
        v-bind="{ ...price_source_custom_api.properties }"
        class="col-6"
      />
    </Field>
    <Field title="Custom API update interval">
      <Counter
        v-model="custom_api_update_interval.value.value"
        :type="CounterType.Seconds"
        v-bind="{ ...custom_api_update_interval.properties }"
      />
    </Field>
    <Field>
      <Order title="Order 1" hint="Order hint">
        <template #toggle>
          <q-btn-toggle
            v-model="order_1_Toggle.value.value"
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
            v-model="order_1_FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_1_FirstCounter.properties }"
          />
          <Counter
            v-model="order_1_SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_1_SecondCounter.properties }"
          />
        </template>
      </Order>
      <Order title="Order 2" hint="Order hint">
        <template #toggle>
          <q-btn-toggle
            v-model="order_2_Toggle.value.value"
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
            v-model="order_2_FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_2_FirstCounter.properties }"
          />
          <Counter
            v-model="order_2_SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_2_SecondCounter.properties }"
          />
        </template>
      </Order>
      <Order title="Order 3" hint="Order hint">
        <template #toggle>
          <q-btn-toggle
            v-model="order_3_Toggle.value.value"
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
            v-model="order_3_FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_3_FirstCounter.properties }"
          />
          <Counter
            v-model="order_3_SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_3_SecondCounter.properties }"
          />
        </template>
      </Order>
      <Order title="Order 4" hint="Order hint">
        <template #toggle>
          <q-btn-toggle
            v-model="order_4_Toggle.value.value"
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
            v-model="order_4_FirstCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_4_FirstCounter.properties }"
          />
          <Counter
            v-model="order_4_SecondCounter.value.value"
            :type="CounterType.FloatCount"
            v-bind="{ ...order_4_SecondCounter.properties }"
          />
        </template>
      </Order>
    </Field>
    <Field title="Max. order age">
      <Counter
        v-model="max_order_age.value.value"
        :type="CounterType.Seconds"
        v-bind="{ ...max_order_age.properties }"
      />
    </Field>
  </div>
</template>
<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent, ref } from 'vue';

import Counter, { CounterType } from '../components/Counter.vue';
import Field from '../components/Field.vue';
import Input, { InputType } from '../components/Input.vue';
import Order from '../components/Order.vue';
import Select from '../components/Select/Index.vue';
import { BtnToggleType, useForm } from '../composables/useForm';

enum FormType {
  Basic,
  Advanced,
}

export default defineComponent({
  name: 'PureMMForm',
  components: { Field, Select, Counter, Input, Order },

  emits: ['update:formType'],

  setup() {
    const { fields } = useForm(ref(StrategyName.PureMarketMaking), true);
    const formType = ref(FormType.Basic);

    return {
      ...fields,
      CounterType,
      InputType,
      formType,
      FormType,
      BtnToggleType,
    };
  },
});
</script>
