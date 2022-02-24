<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders q-mt-md full-width">
    <div class="text-white text-h4 q-mb-lg">
      {{ displaySaveForm ? titleDisplayMap[strategyName] : 'Settings' }}
    </div>
    <q-form>
      <component :is="componentsMap[strategyName]" v-if="!displaySaveForm" />
      <SaveForm v-if="displaySaveForm" :strategy-name="strategyName" />
    </q-form>
  </div>
</template>

<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { computed, defineComponent, PropType } from 'vue';

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
  components: { PureMMForm, SaveForm },
  props: {
    strategyName: {
      type: String as PropType<StrategyName>,
      required: true,
      default: () => StrategyName.PureMarketMaking,
    },
  },

  setup() {
    const step = useSteps();
    const displaySaveForm = computed(() => step.current.value === step.count);

    return { componentsMap, displaySaveForm, titleDisplayMap };
  },
});
</script>
