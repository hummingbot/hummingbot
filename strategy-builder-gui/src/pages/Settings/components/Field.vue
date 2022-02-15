<template>
  <div class="row justify-between items-center q-pb-md border">
    <div v-if="title" class="row text-body1 text-white"> {{ title }} </div>
    <slot />
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  props: {
    title: { type: String, required: false, default: () => '' },
  },
});
</script>

<style lang="scss" scoped>
@use 'sass:map';
.border {
  border-bottom: 2px dashed map.get($colors, 'mono-grey-2') !important;
}
</style>
