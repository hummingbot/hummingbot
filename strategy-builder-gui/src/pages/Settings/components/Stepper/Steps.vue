<template>
  <div class="row q-col-gutter-sm">
    <div v-for="(step, index) in stepsData" :key="index" class="col-12 col-md">
      <Step
        :title="step.title"
        :description="step.description"
        :status="
          currentStep === index + 1
            ? StepStatus.InProgress
            : currentStep > index + 1
            ? StepStatus.Completed
            : StepStatus.NotStarted
        "
      />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import { useSteps } from '../../composables/useSteps';
import Step, { StepStatus } from './Step.vue';

interface StepType {
  title: string;
  description: string;
}

export default defineComponent({
  components: { Step },
  setup() {
    const steps = useSteps();
    const stepsData: StepType[] = [
      {
        title: '1. Choose strategy',
        description: 'Pure market making',
      },
      {
        title: '2. Choose settings',
        description: 'Basic and advanced',
      },
      {
        title: '3. Save settings',
        description: 'Review and save file',
      },
    ];

    return { stepsData, StepStatus, currentStep: steps.current };
  },
});
</script>
