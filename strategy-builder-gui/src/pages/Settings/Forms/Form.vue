<template>
  <q-form @submit="handleSubmit">
    <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders q-mt-md full-width">
      <div class="text-white text-h4 q-mb-lg">
        {{ displaySaveForm ? titleDisplayMap[strategyName] : 'Settings' }}
      </div>
      <component :is="componentsMap[strategyName]" v-if="!displaySaveForm" />
      <SaveForm v-if="displaySaveForm" :strategy-name="strategyName" />
    </div>
    <Pager v-model="currentStep" :file-name="fileName" :file-href="fileHref" />
  </q-form>
</template>

<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { computed, defineComponent } from 'vue';
import { useRoute } from 'vue-router';

import Pager from '../components/Pager/Index.vue';
import { useFileHref } from '../composables/useFileHref';
import { useForm } from '../composables/useForm';
import { useSteps } from '../composables/useSteps';
import PureMMForm from './PureMMForm.vue';
import SaveForm from './SaveForm.vue';

const componentsMap = {
  [StrategyName.PureMarketMaking]: PureMMForm.name,
};

const titleDisplayMap = {
  [StrategyName.PureMarketMaking]: 'Pure Market Making',
};

export default defineComponent({
  components: { PureMMForm, SaveForm, Pager },

  setup() {
    const steps = useSteps();
    const route = useRoute();
    const strategyName = computed(() => route.params.strategyName as StrategyName);
    const { values } = useForm(strategyName, true);
    const fileHref = useFileHref(strategyName); // TODO: sort  values and rename fields, based on template
    const displaySaveForm = computed(() => steps.current.value === steps.count);
    const fileName = computed(
      () => Object.getOwnPropertyDescriptor(values.value, 'fileName')?.value,
    );

    const handleSubmit = () => {
      localStorage.setItem(strategyName.value, JSON.stringify(values.value));
      // eslint-disable-next-line no-console
      console.log(values.value);
    };

    return {
      componentsMap,
      displaySaveForm,
      titleDisplayMap,
      handleSubmit,
      currentStep: steps.current,
      strategyName,
      fileHref,
      fileName,
    };
  },
});
</script>
