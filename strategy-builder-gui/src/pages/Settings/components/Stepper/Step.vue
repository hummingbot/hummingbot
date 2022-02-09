<template>
  <q-card class="q-pt-md q-pb-lg q-px-lg bg-mono-grey-1">
    <div class="row justify-between items-center q-mb-md">
      <div class="text-mono-green-2 text-h6"> Completed </div>
      <q-icon :name="`img:${require('../../assets/status-completed.svg')}`" size="20px" />
    </div>
    <div class="text-white text-h5 q-mb-xs">1. Choose strategy </div>
    <div class="text-mono-grey-3 text-body1"> Pure market making </div>
  </q-card>
</template>

<script>
import { defineComponent, PropType } from 'vue';

export enum StepStatus {
    completed,
    inProgress,
    notStarded,
}
export default defineComponent({
    props: {
        status: {type: Number as PropType<StepStatus>, required: true, default: () => StepStatus.notStarded},
        title: { type: String, requaried: true, default: () => '' },
        desc: { type: String, requaried: true, default: () => '' },
    }
});
</script>

<style></style>
