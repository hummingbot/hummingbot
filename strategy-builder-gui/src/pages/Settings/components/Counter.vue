<template>
  <div class="row justify-center items-center q-gutter-md no-wrap">
    <q-btn
      size="md"
      class="bg-mono-grey-2 q-px-md q-py-xs rounded-borders"
      :disable="modelValue < min + step"
      @click="$emit('update:modelValue', modelValue - step)"
    >
      <span :class="modelValue < min + step ? 'text-mono-grey-4' : 'text-main-green-1'"> - </span>
    </q-btn>
    <span
      class="counter-modelValue text-body1 text-weight-semibold items-center text-center"
      :class="modelValue < min + step ? 'text-mono-grey-4' : 'text-white'"
    >
      {{ displayValue }}{{ counterType }}
    </span>

    <q-btn
      size="md"
      class="bg-mono-grey-2 q-px-md q-py-xs rounded-borders"
      :disable="modelValue > max - step"
      @click="$emit('update:modelValue', modelValue + step)"
    >
      <span :class="modelValue > max - step ? 'text-mono-grey-4' : 'text-main-green-1'"> + </span>
    </q-btn>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, PropType } from 'vue';

export enum CounterType {
  Percentage,
  Seconds,
  CountInt,
  FloatCount,
}

const counterTypesDisplayMap = {
  [CounterType.Percentage]: '%',
  [CounterType.Seconds]: 's',
  [CounterType.CountInt]: '',
  [CounterType.FloatCount]: '',
};

export default defineComponent({
  props: {
    type: {
      type: Number as PropType<CounterType>,
      require: true,
      default: () => CounterType.CountInt,
    },
    min: { type: Number, require: true, default: () => 0 },
    max: { type: Number, require: true, default: () => 0 },
    modelValue: { type: Number, require: true, default: () => 0 },
    step: { type: Number, require: true, default: () => 0 },
  },
  emits: ['update:modelValue'],

  setup(props) {
    const counterType = computed(() => counterTypesDisplayMap[props.type]);
    const displayValue = computed(() =>
      props.modelValue.toFixed(
        props.type === CounterType.Percentage || props.type === CounterType.FloatCount ? 2 : 0,
      ),
    );

    return { counterType, displayValue };
  },
});
</script>

<style lang="scss" scoped>
.counter-modelValue {
  min-width: 45px;
}
</style>
