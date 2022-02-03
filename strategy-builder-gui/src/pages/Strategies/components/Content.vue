<template>
  <div class="flex row q-gutter-x-lg">
    <Box
      class="col"
      :type="BoxType.strategy"
      title="STRATEGIES"
      count="13"
      desc="Hummingbot offers various trading strategies, each with its own set of configurable parameters."
      link-text="Documentation"
      href="/"
      :bg-image-src="require('../assets/strategies-box-robot.svg')"
    />
    <Box class="col" :type="BoxType.exchanges" />
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
