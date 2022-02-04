<template>
  <div class="flex row q-gutter-lg box-wrapper">
    <Box
      class="col-md"
      :type="BoxType.Strategy"
      title="STRATEGIES"
      :count="13"
      desc="Hummingbot offers various trading strategies, each with its own set of configurable parameters."
      link-text="Documentation"
      href="/"
      :bg-image-src="require('../assets/strategies-box-robot.svg')"
    />
    <Box
      class="col-md"
      :type="BoxType.Exchanges"
      title="SUPPORTED EXCHANGES"
      :count="30"
      desc="Hummingbot can be run on a various top tier centralized and decentralized exchanges."
      link-text="Connectors"
      href="/"
      :bg-image-src="require('../assets/strategies-box-chart.svg')"
    />
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Box, { BoxType } from './Box.vue';

export default defineComponent({
  components: { Box },

  setup() {
    return { BoxType };
  },
});
</script>

<style lang="scss" scoped>
@media (max-width: $breakpoint-sm-max) {
}
</style>
