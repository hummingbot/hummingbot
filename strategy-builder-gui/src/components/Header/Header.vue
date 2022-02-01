<template>
  <q-toolbar class="row flex items-center q-mb-lg q-px-none">
    <div class="col">
      <q-item
        style="max-height: 46px; max-width: 56px"
        class="q-px-none q-py-none"
        clickable
        to="/"
      >
        <q-img :src="require('./assets/header-logo.svg')" fit="contain" />
      </q-item>
    </div>
    <div class="col flex justify-end">
      <q-btn
        color="mono-grey-1"
        class="q-py-md q-px-lg text-h6 text-uppercase"
        @click="onClickUpload()"
      >
        Upload strategy
      </q-btn>
    </div>
  </q-toolbar>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  setup() {
    const onClickUpload = () => {
      // eslint-disable-next-line no-console
      console.log('upload click');
    };

    return { onClickUpload };
  },
});
</script>
