<template>
  <div class="row justify-center items-center q-gutter-md no-wrap">
    <q-btn
      size="md"
      class="bg-mono-grey-2 q-px-md q-py-xs rounded-borders"
      :disable="displayValue <= min"
      @click="onClick(-stepValue, name)"
    >
      <span :class="displayValue <= min ? 'text-mono-grey-4' : 'text-main-green-1'">-</span>
    </q-btn>
    <span
      class="counter-value text-body1 text-weight-semibold items-center text-center"
      :class="displayValue <= min ? 'text-mono-grey-4' : 'text-white'"
    >
      {{ displayValue }}{{ counterType }}
    </span>

    <q-btn
      size="md"
      class="bg-mono-grey-2 q-px-md q-py-xs rounded-borders"
      :disable="displayValue >= max"
      @click="onClick(stepValue, name)"
    >
      <span :class="displayValue >= max ? 'text-mono-grey-4' : 'text-main-green-1'">+</span>
    </q-btn>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, PropType } from 'vue';

import { CounterTypes } from './stores/counters';

const counterTypesDisplayMap = {
  [CounterTypes.Percentage]: '%',
  [CounterTypes.Seconds]: 's',
  [CounterTypes.CountInt]: '',
  [CounterTypes.FloatCount]: '',
};

export default defineComponent({
  props: {
    type: {
      type: Number as PropType<CounterTypes>,
      require: true,
      default: () => CounterTypes.CountInt,
    },
    name: { type: String, require: true, default: () => '' },
    min: { type: Number, require: true, default: () => 0 },
    max: { type: Number, require: true, default: () => 0 },
    counterValue: { type: Number, require: true, default: () => 0 },
    stepValue: { type: Number, require: true, default: () => 0 },
    onClick: { type: Function, require: true, default: () => undefined },
  },

  setup(props) {
    const counterType = computed(() => counterTypesDisplayMap[props.type]);
    const displayValue = computed(() =>
      props.type === CounterTypes.Percentage || props.type === CounterTypes.FloatCount
        ? props.counterValue.toFixed(2)
        : props.counterValue,
    );

    return { counterType, displayValue };
  },
});
</script>

<style lang="scss" scoped>
.counter-value {
  min-width: 45px;
}
</style>
