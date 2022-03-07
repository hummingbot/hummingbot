<template>
  <div
    class="flex justify-between items-center q-px-xl q-py-md q-mt-md bg-mono-grey-1 rounded-borders"
  >
    <q-btn
      class="bg-mono-grey-2 text-uppercase text-white q-py-sm"
      flat
      :to="modelValue === 2 ? { name: 'strategies' } : ''"
      @click="$emit('update:modelValue', modelValue === 2 ? modelValue : modelValue - 1)"
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
      v-if="modelValue < stepCount"
      class="bg-main-green-1 text-uppercase text-white q-py-sm"
      flat
      @click="$emit('update:modelValue', modelValue >= stepCount ? modelValue : modelValue + 1)"
    >
      next
    </q-btn>
    <q-btn
      v-if="modelValue === stepCount"
      class="bg-main-green-1 text-uppercase text-white q-py-sm"
      flat
      type="submit"
      :href="fileHref"
      :download="`${fileName}.yml`"
    >
      save
    </q-btn>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import { useSteps } from '../../composables/useSteps';

export default defineComponent({
  props: {
    modelValue: { type: Number, required: true, default: () => 1 },
    handleSubmit: { type: Function, required: false, default: () => ({}) },
    fileHref: { type: String, required: true, default: () => '' },
    fileName: { type: String, required: true, default: () => '' },
  },
  emits: ['update:modelValue'],
  setup() {
    const steps = useSteps();
    return { stepCount: steps.count };
  },
});
</script>

<style lang="scss" scoped>
.step {
  width: 8px;
  height: 8px;

  border-radius: 50%;
}
</style>
