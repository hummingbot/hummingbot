<template>
  <div class="column">
    <Steps :in-progress-step="currentStep" />
    <Form
      :strategy-name="currentStrategyName"
      :title="currentStep === stepCount ? titleDisplayMap[currentStrategyName] : 'Settings'"
      :display-save-form="currentStep === stepCount"
    />
    <Pager v-model="currentStep" :step-count="stepCount" :handle-submit="handleSubmit" />
  </div>
</template>

<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent, ref } from 'vue';
import { useRoute } from 'vue-router';

import Pager from './components/Pager/Index.vue';
import Steps from './components/Stepper/Steps.vue';
import { useForm } from './composables/useForm';
import Form from './Forms/Form.vue';

const titleDisplayMap = {
  [StrategyName.PureMarketMaking]: 'Pure Market Making',
};

export default defineComponent({
  components: { Steps, Pager, Form },
  setup() {
    const route = useRoute();
    const currentStrategyName = route.params.strategyName as StrategyName;
    const { values } = useForm(currentStrategyName);
    const currentStep = ref(2);
    const stepCount = 3;

    const handleSubmit = () => {
      // eslint-disable-next-line no-console
      console.log(values.value);
    };

    return {
      currentStep,
      stepCount,
      handleSubmit,
      StrategyName,
      currentStrategyName,
      titleDisplayMap,
    };
  },
});
</script>
