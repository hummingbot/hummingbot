<template>
  <div class="column">
    <Steps :in-progress-step="currentStep" />
    <Form
      title="Settings"
      :current-step="currentStep"
      :step-count="stepCount"
      strategy-name="Pure Market Making"
    >
      <SettingsForm v-if="currentStep < stepCount" :form="FormList.PureMarketMaking" />
      <SaveForm v-if="currentStep === stepCount" :form="FormList.PureMarketMaking" />
    </Form>
    <Pager v-model="currentStep" :step-count="stepCount" :handle-submit="handleSubmit" />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';

import Pager from './components/Pager/Index.vue';
import Steps from './components/Stepper/Steps.vue';
import { useSettingsForm } from './composables/useSettingsForm';
import Form from './Forms/Form.vue';
import SaveForm from './Forms/SaveForm.vue';
import SettingsForm from './Forms/SettingsForm.vue';
import { FormList } from './types';

export default defineComponent({
  components: { Steps, Pager, Form, SettingsForm, SaveForm },
  setup() {
    const { values } = useSettingsForm(FormList.PureMarketMaking); // TODO: calculate via route
    const currentStep = ref(2);
    const stepCount = 3;

    const handleSubmit = () => {
      // eslint-disable-next-line no-console
      console.log(values.value);
    };

    return { currentStep, stepCount, handleSubmit, FormList };
  },
});
</script>
