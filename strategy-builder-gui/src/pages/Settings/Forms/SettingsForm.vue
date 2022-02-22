<template>
  <component :is="componentsMap[strategyName]" />
</template>
<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent, PropType } from 'vue';

import PureMMForm from './PureMMForm.vue';

const componentsMap = {
  [StrategyName.PureMarketMaking]: PureMMForm.name,
};

export default defineComponent({
  components: { PureMMForm },
  props: {
    strategyName: {
      type: String as PropType<StrategyName>,
      required: true,
      default: () => StrategyName.PureMarketMaking,
    },
  },

  setup() {
    return { componentsMap };
  },
});
</script>
