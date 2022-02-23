<template>
  <div class="bg-mono-grey-1 q-px-xl q-py-lg rounded-borders q-mt-md full-width">
    <div class="text-white text-h4 q-mb-lg">{{ title }}</div>
    <q-form>
      <component :is="componentsMap[strategyName]" v-if="!displaySaveForm" />
      <SaveForm v-if="displaySaveForm" :strategy-name="strategyName" />
    </q-form>
  </div>
</template>

<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent, PropType } from 'vue';

import PureMMForm from './PureMMForm.vue';
import SaveForm from './SaveForm.vue';

const componentsMap = {
  [StrategyName.PureMarketMaking]: PureMMForm.name,
};

export default defineComponent({
  components: { PureMMForm, SaveForm },
  props: {
    title: { type: String, required: false, default: () => '' },
    strategyName: {
      type: String as PropType<StrategyName>,
      required: true,
      default: () => StrategyName.PureMarketMaking,
    },
    displaySaveForm: { type: Boolean, required: true, default: () => false },
  },

  setup() {
    return { componentsMap };
  },
});
</script>
