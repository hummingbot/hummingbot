<template>
  <div class="column">
    <Steps />
    <Form :strategy-name="currentStrategyName" />
    <Pager v-model="currentStep" :handle-submit="handleSubmit" />
  </div>
</template>

<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent } from 'vue';
import { useRoute } from 'vue-router';

import Pager from './components/Pager/Index.vue';
import Steps from './components/Stepper/Steps.vue';
import { useForm } from './composables/useForm';
import { useSteps } from './composables/useSteps';
import Form from './Forms/Form.vue';

export default defineComponent({
  components: { Steps, Pager, Form },
  setup() {
    const route = useRoute();
    const step = useSteps();
    const currentStrategyName = route.params.strategyName as StrategyName;
    const { values } = useForm(currentStrategyName);

    const handleSubmit = () => {
      // eslint-disable-next-line no-console
      console.log(values.value);
    };

    return {
      currentStep: step.current,
      handleSubmit,
      currentStrategyName,
    };
  },
});
</script>
