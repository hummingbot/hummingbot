<template>
  <div
    class="row items-center q-pb-md border"
    :class="type === FieldType.Orders ? 'justify-around' : 'justify-between'"
  >
    <div v-if="title" class="row text-body1 text-white items-center">
      {{ title }}
      <q-icon v-if="hint" :name="`img:${require('../hint.svg')}`" class="q-ml-xs">
        <q-tooltip
          class="bg-mono-grey-2 text-white text-body2"
          anchor="top middle"
          self="center right"
          max-width="300px"
        >
          {{ hint }}
        </q-tooltip>
      </q-icon>
    </div>
    <slot />
  </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

import { FieldType } from '../stores/form.types';

export default defineComponent({
  props: {
    title: { type: String, required: false, default: () => '' },
    hint: { type: String, required: false, default: () => '' },
    ordersField: { type: Boolean, required: false, default: () => false },
    type: { type: Number as PropType<FieldType>, required: true, default: () => FieldType.Input },
  },

  setup() {
    return { FieldType };
  },
});
</script>

<style lang="scss" scoped>
@use 'sass:map';
.border {
  border-bottom: 2px dashed map.get($colors, 'mono-grey-2') !important;
}

.border:last-child {
  border: none !important;
  padding-bottom: 0;
}
</style>
