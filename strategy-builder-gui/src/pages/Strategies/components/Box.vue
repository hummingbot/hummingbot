<template>
  <q-card id="card" style="" class="card">
    <q-card-section horizontal class="flex row full-height">
      <q-card-section
        horizontal
        class="q-px-lg q-py-lg flex items-center justify-center text-white text-h2 q-mr-lg border-blue"
        style="min-width: 124px"
      >
        <img v-if="type === 'strategy'" src="~assets/strategies-box-number.svg" class="q-mr-xs" />
        {{ box.count }}
      </q-card-section>
      <q-card-section
        class="flex column items-start justify-center q-pl-none"
        style="padding-right: 135px"
      >
        <div class="text-h4 text-white q-mb-xs"> {{ box.title }} </div>
        <div class="text-body-1 q-mb-sm" style="line-height: normal">
          {{ box.desc }}
        </div>
        <a href="box.href" class="text-normal text-blue text-h5">
          {{ box.linkText }}
          ➜
        </a>
      </q-card-section>
    </q-card-section>
    <div class="box-image flex items-end">
      <img src="~assets/strategies-box-robot.svg" />
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

.card {
  background: map.get($colors, 'mono-grey-1');
}

.text-blue {
  color: map.get($colors, 'mono-blue');
}

.box-image {
  position: absolute;
  right: 0;
  bottom: 0;
}
</style>
