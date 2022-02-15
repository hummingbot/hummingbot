<template>
  <div class="column items-center">
    <div class="text-body1 text-white q-mb-sm">{{ title }}</div>
    <div class="row full-width justify-between q-mb-md">
      <q-btn
        :class="
          modelValue === OrderStatus.Sell
            ? 'bg-mono-grey-2 text-white'
            : 'bg-mono-grey-1 text-mono-grey-3'
        "
        :ripple="false"
        @click="$emit('update:modelValue', OrderStatus.Sell)"
      >
        SELL
      </q-btn>
      <q-btn
        :class="
          modelValue === OrderStatus.Buy
            ? 'bg-mono-grey-2 text-white'
            : 'bg-mono-grey-1 text-mono-grey-3'
        "
        :ripple="false"
        @click="$emit('update:modelValue', OrderStatus.Buy)"
      >
        BUY
      </q-btn>
    </div>
    <div class="column q-col-gutter-md">
      <slot />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

import { OrderStatus } from '../stores/settingsForm';

export default defineComponent({
  props: {
    modelValue: {
      type: String as PropType<OrderStatus>,
      require: true,
      default: () => OrderStatus.Buy,
    },
    title: { type: String, require: false, default: () => '' },
  },
  emits: ['update:modelValue'],
  setup() {
    return { OrderStatus };
  },
});
</script>

<style></style>
