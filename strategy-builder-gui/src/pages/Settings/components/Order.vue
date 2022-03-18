<template>
  <div class="column items-center order">
    <div class="text-body1 text-white q-mb-sm flex items-center">
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
    <div class="q-mb-md full-width">
      <slot name="toggle" />
    </div>
    <div class="column q-gutter-y-md full-width">
      <slot name="counters" />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  props: {
    title: { type: String, require: false, default: () => '' },
    hint: { type: String, required: false, default: () => '' },
  },
});
</script>

<style lang="scss" scoped>
.order {
  max-width: 140px;
  width: 100%;
}
</style>
