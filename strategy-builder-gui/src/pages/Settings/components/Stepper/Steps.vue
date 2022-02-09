<template>
  <div class="row q-gutter-sm">
    <div v-for="(step, index) in steps" :key="index" class="col-12 col-md">
      <Step
        :title="step.title"
        :desc="step.desc"
        :status="
          startedStep === index + 1
            ? StepStatus.inProgress
            : startedStep > index + 1
            ? StepStatus.completed
            : StepStatus.notStarded
        "
      />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Step, { StepStatus } from './Step.vue';

interface StepType {
  title: string;
  desc: string;
}

export default defineComponent({
  components: { Step },
  props: {
    startedStep: { type: Number, required: true, default: () => 0 },
  },
  setup() {
    const steps: StepType[] = [
      {
        title: '1. Choose strategy',
        desc: 'Pure market making',
      },
      {
        title: '2. Choose settings',
        desc: 'Basic and advanced',
      },
      {
        title: '3. Save settings',
        desc: 'Review and save file',
      },
    ];

    return { steps, StepStatus };
  },
});
</script>

<style></style>
