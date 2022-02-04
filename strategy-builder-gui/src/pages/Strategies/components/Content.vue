<template>
  <div class="row q-col-gutter-lg">
    <div class="col-xs-12 col-md">
      <Box
        :type="BoxType.Strategy"
        title="Strategies"
        :count="13"
        desc="Hummingbot offers various trading strategies, each with its own set of configurable parameters."
        link-text="Documentation"
        href="/"
        :bg-image-src="require('../assets/strategies-box-robot.svg')"
      />
    </div>
    <div class="col-xs-12 col-md">
      <Box
        :type="BoxType.Exchanges"
        title="Supported exchanges"
        :count="30"
        desc="Hummingbot can be run on a various top tier centralized and decentralized exchanges."
        link-text="Connectors"
        href="/"
        :bg-image-src="require('../assets/strategies-box-chart.svg')"
      />
    </div>
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
