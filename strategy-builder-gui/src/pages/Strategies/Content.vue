<template>
  <div class="row q-col-gutter-lg">
    <div class="col-xs-12 col-md">
      <FeatureBox
        :type="FeatureBoxType.Strategy"
        title="Strategies"
        :count="13"
        description="Hummingbot offers various trading strategies, each with its own set of configurable parameters."
        link-text="Documentation"
        href="/"
        :bg-image-src="require('./strategies-box-robot.svg')"
      />
    </div>
    <div class="col-xs-12 col-md">
      <FeatureBox
        :type="FeatureBoxType.Exchanges"
        title="Supported exchanges"
        :count="30"
        description="Hummingbot can be run on a various top tier centralized and decentralized exchanges."
        link-text="Connectors"
        href="/"
        :bg-image-src="require('./strategies-box-chart.svg')"
      />
    </div>
  </div>
  <div class="column">
    <div class="row justify-between items-center">
      <div class="text-white text-h4 q-mt-lg q-mb-md col"> Choose Your Strategy </div>
      <div class="strategies-select flex items-center justify-center full-width">
        <q-select
          v-model="category"
          borderless
          input-class="flex items-center justify-center"
          :options="categories"
          rounded
          :dropdown-icon="`img:${require('./arrow-bottom.svg')}`"
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
          :description="strategy.description"
          :file-href="strategy.fileHref"
          :strategy-name="strategy.strategyName"
        />
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';

import { useStrategies } from '../../composables/useStrategies';
import { StrategyCategory } from '../../stores/strategies';
import FeatureBox, { FeatureBoxType } from './components/FeatureBox/Index.vue';
import StrategyBox from './components/StrategyBox/Index.vue';
import { useStrategiesByCategory } from './composables/useStrategiesByCategory';

export default defineComponent({
  components: { FeatureBox, StrategyBox },

  setup() {
    const category = ref(StrategyCategory.All);
    const { categories } = useStrategies();
    const strategiesByCategory = useStrategiesByCategory(category);

    return {
      FeatureBoxType,
      strategies: strategiesByCategory.values,
      category,
      categories,
    };
  },
});
</script>

<style lang="scss">
@use 'sass:map';
.strategies-select {
  max-width: 150px;
}
.strategies-select .q-field__control {
  display: flex;
  align-items: center;
  justify-content: center;
}
.strategies-select .q-icon img {
  max-width: 12px !important;
  max-height: 6px !important;
}
</style>
