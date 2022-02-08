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
          v-model="selectModel"
          borderless
          input-class="flex items-center justify-center"
          :options="strategiesObj.options"
          rounded
          :dropdown-icon="`img:${require('../assets/arrow-bottom.svg')}`"
          :display-value="selectModel"
          :label-slot="false"
          popup-content-class="bg-mono-grey-2 q-px-md q-py-md"
          options-selected-class="bg-mono-grey-1 rounded-borders"
          @update:model-value="(val) => onSelectUpdate(val)"
        />
      </div>
    </div>
    <div class="row q-col-gutter-lg">
      <div
        v-for="strategie in strategiesObj.strategies"
        :key="strategie.place"
        class="col-12 col-md-6 col-lg-3"
      >
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
import { defineComponent, ref } from 'vue';

import FeatureBox, { FeatureBoxType } from './FeatureBox.vue';
import {
  StrategyCategory,
  useStrategiesFilter,
} from './StrategyBox/composables/useStrategiesFilter';
import StrategyBox from './StrategyBox/StrategyBox.vue';

export default defineComponent({
  components: { FeatureBox, StrategyBox },

  setup() {
    const strategiesObj = ref(useStrategiesFilter(StrategyCategory.All));
    const selectModel = ref(strategiesObj.value.options[0]);

    const onSelectUpdate = (value: StrategyCategory) => {
      strategiesObj.value = useStrategiesFilter(value);
    };

    return {
      FeatureBoxType,
      strategiesObj,

      selectModel,
      onSelectUpdate,
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
