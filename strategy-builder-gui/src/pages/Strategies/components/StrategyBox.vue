<template>
  <q-card class="bg-mono-grey-1 overflow-hidden rounded-borders full-height q-px-md q-py-md">
    <q-card-section horizontal class="flex row full-height">
      <q-card-section class="q-py-none q-px-none q-pr-md">
        <div class="text-white text-h6 q-mb-sm">{{ title }}</div>
        <div class="text-mono-grey-4 text-body2 q-mb-lg">
          {{ desc }}
        </div>
        <div class="row q-gutter-sm">
          <q-btn class="bg-mono-grey-2 rounded-borders" padding="sm" :href="fileHref">
            <q-icon :name="'img:' + require('../assets/file.svg')" size="10px" />
          </q-btn>
          <q-btn class="bg-mono-green-2 rounded-borders" padding="sm" :href="startHref">
            <q-icon :name="'img:' + require('../assets/play.svg')" size="10px" />
          </q-btn>
        </div>
      </q-card-section>
      <q-card-section class="fit q-py-none q-px-none place">
        <div class="row bg-mono-grey-2 rounded-borders q-py-none q-px-sm">
          <div class="col q-mr-xs text-h6 text-white">{{ place }}</div>
          <div class="col">
            <q-icon :name="`img:${require(`../assets/place-${placeType}.svg`)}`" size="8px" />
          </div>
        </div>
      </q-card-section>
    </q-card-section>
  </q-card>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

export type StrategyBoxPlaceType = keyof { equal: string; lt: string; gt: string };

export default defineComponent({
  props: {
    place: { type: Number, requaried: true, default: () => 0 },
    placeType: {
      type: String as PropType<StrategyBoxPlaceType>,
      requaried: true,
      default: () => 'equal',
    },
    title: { type: String, requaried: true, default: () => '' },
    desc: { type: String, requaried: true, default: () => '' },
    fileHref: { type: String, default: () => '/' },
    startHref: { type: String, requaried: true, default: () => '/' },
  },
});
</script>

<style lang="scss" scoped>
@use 'sass:map';

.place {
  max-width: 36px;
}
</style>
