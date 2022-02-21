<template>
  <div
    class="flex justify-between items-center q-px-xl q-py-md q-mt-md bg-mono-grey-1 rounded-borders"
  >
    <q-btn
      class="bg-mono-grey-2 text-uppercase text-white q-py-sm"
      flat
      :to="modelValue === 2 ? 'strategies' : ''"
      @click="$emit('update:modelValue', modelValue === 0 ? modelValue : modelValue - 1)"
    >
      back
    </q-btn>
    <div class="row q-gutter-sm">
      <div
        v-for="n in stepCount"
        :key="n"
        class="step"
        :class="
          modelValue === n
            ? 'bg-mono-grey-3'
            : modelValue > n
            ? 'bg-main-green-1'
            : 'bg-mono-grey-2'
        "
      />
    </div>
    <q-btn
      class="bg-main-green-1 text-uppercase text-white q-py-sm"
      flat
      @click="
        () => {
          $emit('update:modelValue', modelValue >= stepCount ? modelValue : modelValue + 1);
          if (modelValue === stepCount) {
            handleSubmit();
          }
        }
      "
    >
      {{ modelValue === stepCount ? 'save' : 'next' }}
    </q-btn>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  props: {
    modelValue: { type: Number, required: true, default: () => 1 },
    stepCount: { type: Number, required: true, default: () => 3 },
    handleSubmit: { type: Function, required: false, default: () => ({}) },
  },
  emits: ['update:modelValue'],
});
</script>

<style lang="scss" scoped>
.step {
  width: 8px;
  height: 8px;

  border-radius: 50%;
}
</style>
