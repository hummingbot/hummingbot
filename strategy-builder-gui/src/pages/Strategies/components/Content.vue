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
    <div class="row justify-between items-center">
      <div class="text-white text-h4 q-mt-lg q-mb-md col"> Choose Your Strategy </div>
      <div class="select flex items-center justify-center full-width">
        <q-select
          v-model="category"
          borderless
          input-class="flex items-center justify-center"
          :options="options"
          rounded
          :dropdown-icon="`img:${require('../assets/arrow-bottom.svg')}`"
          :display-value="category"
          :label-slot="false"
          popup-content-class="bg-mono-grey-2 q-px-md q-py-md"
          options-selected-class="bg-mono-grey-1 rounded-borders"
        />
      </div>
    </div>
    <div class="row q-col-gutter-lg">
      <div v-for="strategy in strategies" :key="strategy.place" class="col-12 col-md-6 col-lg-3">
        <StrategyBox
          :place="strategy.place"
          :place-type="strategy.placeType"
          :title="strategy.title"
          :desc="strategy.desc"
          :file-href="strategy.fileHref"
          :start-href="strategy.startHref"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';

import { StrategyCategory } from '../stores/strategies';
import FeatureBox, { FeatureBoxType } from './FeatureBox.vue';
import { useStrategiesFilter } from './StrategyBox/composables/useStrategiesFilter';
import StrategyBox from './StrategyBox/StrategyBox.vue';

export default defineComponent({
  components: { FeatureBox, StrategyBox },

  setup() {
    const category = ref(StrategyCategory.All);
    const { strategies, options } = useStrategiesFilter(category);

    return {
      FeatureBoxType,
      strategies,
      category,
      options,
    };
  },
});
</script>

<style lang="scss">
@use 'sass:map';
.select {
  max-width: 150px;
}
.select .q-field__control {
  display: flex;
  align-items: center;
  justify-content: center;
}
.select .q-icon img {
  max-width: 12px !important;
  max-height: 6px !important;
}
</style>
