<template>
  <q-card class="bg-mono-grey-1 overflow-hidden rounded-borders">
    <q-card-section horizontal class="flex row full-height">
      <q-card-section
        horizontal
        class="q-px-lg q-py-lg flex items-center justify-center text-white text-h2 q-mr-lg rounded-borders border-blue card-counter"
      >
        <img
          v-if="type === BoxType.strategy"
          :src="require('../assets/strategies-box-number.svg')"
          class="q-mr-xs"
        />
        {{ count }} <span v-if="type === 'exchanges'" class="color-green"> +</span>
      </q-card-section>
      <q-card-section class="flex column items-start justify-center q-pl-none col-7">
        <div class="text-h4 text-white q-mb-xs"> {{ title }} </div>
        <div class="text-body-1 q-mb-sm line-normal">
          {{ desc }}
        </div>
        <a href="box.href" class="text-normal text-mono-blue text-h5">
          {{ linkText }}
          ➜
        </a>
      </q-card-section>
    </q-card-section>
    <div class="absolute-bottom-right flex items-end">
      <img :src="bgImageSrc" />
    </div>
  </q-card>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

export enum BoxType {
  'strategy',
  'exchanges',
}

export default defineComponent({
  props: {
    type: { type: Number as PropType<BoxType>, requaried: true, default: () => BoxType.strategy },
    count: { type: Number, requaried: true, default: () => 0 },
    title: { type: String, requaried: true, default: () => '' },
    desc: { type: String, requaried: true, default: () => '' },
    href: { type: String, default: () => '/' },
    linkText: { type: String, requaried: true, default: () => '' },
    bgImageSrc: { type: String, requaried: true, default: () => '' },
  },
  setup() {
    return { BoxType };
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
