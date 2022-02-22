<template>
  <div class="">
    <div class="bg-mono-grey-2 column text-white text-h6 rounded-borders q-py-md q-px-md q-mb-lg">
      <div class="border row justify-between q-pb-sm">
        <span>Binance</span>
        <span>VALUE</span>
      </div>
      <div class="row justify-between q-pt-sm">
        <span>Order Size</span>
        <span>VALUE</span>
      </div>
    </div>
    <div class="column text-white text-body1">
      File name
      <Input
        v-model="fileName.value.value"
        :type="InputType.Text"
        v-bind="{ ...fileName.properties }"
        class="col-12 q-mt-sm"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent, PropType } from 'vue';

import Input, { InputType } from '../components/Input.vue';
import { useForm } from '../composables/useForm';

export default defineComponent({
  components: { Input },
  props: {
    form: {
      type: String as PropType<StrategyName>,
      required: true,
      default: () => StrategyName.PureMarketMaking,
    },
  },

  setup(props) {
    const { settingsForm } = useForm(props.form);

    return { ...settingsForm, InputType };
  },
});
</script>

<style lang="scss" scoped>
@use 'sass:map';
.border {
  border-bottom: 2px dashed map.get($colors, 'mono-grey-3') !important;
}
</style>
