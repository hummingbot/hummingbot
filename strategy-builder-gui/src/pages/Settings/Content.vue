<template>
  <div class="column">
    <Steps :in-progress-step="currentStep" />
    <Form v-if="currentStep < 3" />
    <Pager
      :step="currentStep"
      :step-count="3"
      @update:step="(nextStep) => (currentStep = nextStep)"
    />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';

import Pager from './components/Pager/Index.vue';
import Steps from './components/Stepper/Steps.vue';
import Form from './Form.vue';

export default defineComponent({
  components: { Steps, Pager, Form },
  setup() {
    const currentStep = ref(2);

    return { currentStep };
  },
});
</script>
