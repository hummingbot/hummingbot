<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders q-mt-md full-width">
    <div class="text-white text-h4 q-mb-lg">{{ displayTitle }}</div>
    <q-form>
      <slot />
    </q-form>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent } from 'vue';

export default defineComponent({
  props: {
    title: { type: String, required: false, default: () => '' },
    currentStep: { type: Number, required: true, default: () => 2 },
    stepCount: { type: Number, required: true, default: () => 3 },
    strategyName: { type: String, required: false, default: () => '' },
  },
  setup(props) {
    const displayTitle = computed(() =>
      props.currentStep === props.stepCount ? props.strategyName : props.title,
    );

    return { displayTitle };
  },
});
</script>
