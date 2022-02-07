<template>
  <div class="row q-col-gutter-lg">
    <div class="col-xs-12 col-md">
      <FeatureBox
        :type="FeatureBoxType.Strategy"
        title="Strategies"
        :count="13"
        desc="Hummingbot offers various trading strategies, each with its own set of configurable parameters."
        link-text="Documentation"
        href="/"
        :bg-image-src="require('../assets/strategies-box-robot.svg')"
      />
    </div>
    <div class="col-xs-12 col-md">
      <FeatureBox
        :type="FeatureBoxType.Exchanges"
        title="Supported exchanges"
        :count="30"
        desc="Hummingbot can be run on a various top tier centralized and decentralized exchanges."
        link-text="Connectors"
        href="/"
        :bg-image-src="require('../assets/strategies-box-chart.svg')"
      />
    </div>
  </div>
  <div class="column">
    <div class="text-white text-h4 q-mt-lg q-mb-md"> Choose Your Strategy </div>
    <div class="row q-col-gutter-lg">
      <div v-for="strategie in strategies" :key="strategie.place" class="col-12 col-md-6 col-lg-3">
        <StrategyBox
          :place="strategie.place"
          :place-type="strategie.placeType"
          :title="strategie.title"
          :desc="strategie.desc"
          :file-href="strategie.fileHref"
          :start-href="strategie.startHref"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import FeatureBox, { FeatureBoxType } from './FeatureBox.vue';
import { useStrategiesFilter } from './StrategyBox/composables/useStrategiesFilter';
import StrategyBox from './StrategyBox/StrategyBox.vue';

export default defineComponent({
  components: { FeatureBox, StrategyBox },

  setup() {
    const strategies = useStrategiesFilter();
    return { FeatureBoxType, strategies };
  },
});
</script>
