<template>
  <q-card
    class="q-pt-md q-pb-lg q-px-lg rounded-borders"
    :class="status === StepStatus.InProgress ? 'bg-mono-grey-2' : 'bg-mono-grey-1'"
  >
    <div class="row justify-between items-center q-mb-md">
      <div
        class="text-h6"
        :class="status === StepStatus.Completed ? 'text-mono-green-2' : 'text-mono-grey-3'"
      >
        {{ status }}
      </div>
      <q-icon
        :name="`img:${require(`../../assets/status-${
          status === StepStatus.Completed ? 'completed' : 'in-progress'
        }.svg`)}`"
        size="20px"
      />
    </div>
    <div class="text-white text-h5 q-mb-xs"> {{ title }} </div>
    <div class="text-mono-grey-3 text-body1"> {{ desc }} </div>
  </q-card>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

export enum StepStatus {
  Completed = 'Completed',
  InProgress = 'In Progress',
  NotStarted = 'Not started',
}

export default defineComponent({
  props: {
    status: {
      type: String as PropType<StepStatus>,
      required: true,
      default: () => StepStatus.Completed,
    },
    title: { type: String, requaried: true, default: () => '' },
    desc: { type: String, requaried: true, default: () => '' },
  },
  setup() {
    return { StepStatus };
  },
});
</script>

<style></style>
