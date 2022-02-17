<template>
  <q-card class="bg-mono-grey-1 overflow-hidden rounded-borders full-height">
    <q-card-section horizontal class="flex row full-height">
      <q-card-section
        horizontal
        class="q-px-lg q-py-lg flex items-center justify-center text-white text-h2 q-mr-lg rounded-borders card-counter"
        :class="type === FeatureBoxType.Strategy ? 'border-blue' : 'border-green'"
      >
        <q-img
          v-if="type === FeatureBoxType.Strategy"
          :src="require('./feature-box-number.svg')"
          class="q-mr-xs"
          fit="contain"
          img-class="absolute"
          no-transition
          no-spinner
          width="16px"
          height="13px"
          position="top right"
        />
        {{ count }}
        <span v-if="type === FeatureBoxType.Exchanges" class="text-green q-ml-xs"> +</span>
      </q-card-section>
      <q-card-section class="flex column items-start justify-center q-pl-none col-7">
        <div class="text-h4 text-white q-mb-xs text-uppercase"> {{ title }} </div>
        <div class="text-body1 q-mb-sm line-normal">
          {{ description }}
        </div>
        <a
          :href="href"
          class="text-normal text-body1 text-weight-semibold"
          :class="type === FeatureBoxType.Strategy ? 'text-mono-blue' : 'text-mono-green'"
        >
          {{ linkText }}
          ➜
        </a>
      </q-card-section>
    </q-card-section>
    <q-img
      :src="bgImageSrc"
      fit="contain"
      class="absolute-bottom-right gt-xs"
      width="115px"
      position="right bottom"
      no-spinner
      no-transition
    />
  </q-card>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

export enum FeatureBoxType {
  Strategy,
  Exchanges,
}

export default defineComponent({
  props: {
    type: {
      type: Number as PropType<FeatureBoxType>,
      requaried: true,
      default: () => FeatureBoxType.Strategy,
    },
    count: { type: Number, requaried: true, default: () => 0 },
    title: { type: String, requaried: true, default: () => '' },
    description: { type: String, requaried: true, default: () => '' },
    href: { type: String, default: () => '/' },
    linkText: { type: String, requaried: true, default: () => '' },
    bgImageSrc: { type: String, requaried: true, default: () => '' },
  },
  setup() {
    return { FeatureBoxType };
  },
});
</script>

<style lang="scss" scoped>
@use 'sass:map';

.border-blue {
  border: 2px solid map.get($colors, 'mono-blue') !important;
}

.border-green {
  border: 2px solid map.get($colors, 'mono-green') !important;
}

.card-counter {
  min-width: 124px;
}

.line-normal {
  line-height: normal;
}
</style>
