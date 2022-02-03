<template>
  <q-card class="bg-mono-grey-1 overflow-hidden rounded-borders">
    <q-card-section horizontal class="flex row full-height">
      <q-card-section
        horizontal
        class="q-px-lg q-py-lg flex items-center justify-center text-white text-h2 q-mr-lg rounded-borders card-counter"
      >
        <img
          v-if="type === 'strategy'"
          :src="require('../assets/strategies-box-number.svg')"
          class="q-mr-xs"
        />
        {{ box.count }}
      </q-card-section>
      <q-card-section class="flex column items-start justify-center q-pl-none col-7">
        <div class="text-h4 text-white q-mb-xs"> {{ title }} </div>
        <div class="text-body-1 q-mb-sm line-normal">
          {{ box.desc }}
        </div>
          {{ box.linkText }}
        <a href="box.href" class="text-normal text-mono-blue text-h5">
          ➜
        </a>
      </q-card-section>
    </q-card-section>
      <img :src="require('../assets/strategies-box-robot.svg')" />
    <div class="absolute-bottom-right flex items-end">
    </div>
  </q-card>
</template>

<script lang="ts">
import { defineComponent, PropType, ref } from 'vue';

import { strategiesBox } from '../stores/box';

type BoxType = 'strategy' | 'exchanges';

export default defineComponent({
  props: {
    type: { type: String as PropType<BoxType>, requaried: true, default: () => 'strategy' },
  },
  setup(props) {
    const box = ref(props.type === 'strategy' ? strategiesBox : strategiesBox);

    return { box };
  },
});
</script>

<style lang="scss" scoped>
@use 'sass:map';

.border-blue {
  border: 2px solid map.get($colors, 'mono-blue') !important;
}

.card-counter {
  min-width: 124px;
}

.line-normal {
  line-height: normal;
}
</style>
