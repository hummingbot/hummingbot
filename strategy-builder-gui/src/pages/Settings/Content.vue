<template>
  <div class="column">
    <Steps :in-progress-step="currentStep" />
    <Form :title="currentStep === stepCount ? 'Pure Market Making' : 'Settings'">
      <SettingsForm v-if="currentStep < stepCount" :form="StrategyName.PureMarketMaking" />
      <SaveForm v-if="currentStep === stepCount" :form="StrategyName.PureMarketMaking" />
    </Form>
    <Pager v-model="currentStep" :step-count="stepCount" :handle-submit="handleSubmit" />
  </div>
</template>

<script lang="ts">
import { StrategyName } from 'src/stores/strategies';
import { defineComponent, ref } from 'vue';

import Pager from './components/Pager/Index.vue';
import Steps from './components/Stepper/Steps.vue';
import { useSettingsForm } from './composables/useSettingsForm';
import Form from './Forms/Form.vue';
import SaveForm from './Forms/SaveForm.vue';
import SettingsForm from './Forms/SettingsForm.vue';

export default defineComponent({
  components: { Steps, Pager, Form, SettingsForm, SaveForm },
  setup() {
    const { values } = useSettingsForm(StrategyName.PureMarketMaking); // TODO: calculate via route
    const currentStep = ref(2);
    const stepCount = 3;

    const handleSubmit = () => {
      // eslint-disable-next-line no-console
      console.log(values.value);
    };

    return { currentStep, stepCount, handleSubmit, StrategyName };
  },
});
</script>
