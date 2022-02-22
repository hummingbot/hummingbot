<template>
  <q-card class="bg-mono-grey-1 overflow-hidden rounded-borders full-height q-pl-md q-py-md">
    <q-card-section horizontal class="flex row full-height">
      <q-card-section class="q-py-none q-px-none col-9 column">
        <div class="text-white text-h6 q-mb-sm">{{ title }}</div>
        <div class="text-mono-grey-4 text-body2 q-mb-lg">
          {{ description }}
        </div>
        <div class="row q-gutter-sm q-mt-auto">
          <q-btn class="bg-mono-grey-2 rounded-borders" padding="sm" :to="fileHref">
            <q-icon :name="'img:' + require('./file.svg')" size="10px" />
          </q-btn>
          <q-btn
            class="bg-mono-green-2 rounded-borders"
            padding="sm"
            :to="{ name: 'settings', params: { strategyName } }"
          >
            <q-icon :name="'img:' + require('./play.svg')" size="10px" />
          </q-btn>
        </div>
      </q-card-section>
      <q-card-section class="q-py-none q-px-none q-pr-md flex column justify-start items-end col-3">
        <div class="row bg-mono-grey-2 rounded-borders q-py-none q-px-sm col-auto">
          <div class="col q-mr-xs text-h6 text-white q-mr-xs">{{ place }}</div>
          <div class="col flex items-center justify-center">
            <q-icon :name="`img:${require(`./place-${placeType}.svg`)}`" size="8px" />
          </div>
        </div>
      </q-card-section>
    </q-card-section>
  </q-card>
</template>

<script lang="ts">
import { StrategyName } from 'src/composables/useStrategies';
import { defineComponent, PropType } from 'vue';

export default defineComponent({
  props: {
    place: { type: Number, requaried: true, default: () => 0 },
    placeType: {
      type: String as PropType<'equal' | 'lt' | 'gt'>,
      requaried: true,
      default: () => 'equal',
    },
    title: { type: String, requaried: true, default: () => '' },
    description: { type: String, requaried: true, default: () => '' },
    fileHref: { type: String, default: () => '/' },
    strategyName: { type: String, requaried: true, default: () => StrategyName.PureMarketMaking },
  },
});
</script>
