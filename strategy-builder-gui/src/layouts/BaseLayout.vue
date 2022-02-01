<template>
  <q-layout view="lHh Lpr lFf" class="flex column">
    <q-page-container class="q-py-lg q-px-xl flex self-center full-width" style="max-width: 1440px">
      <Header />
      <slot />
    </q-page-container>
  </q-layout>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Header from '../components/Header/Header.vue';

export default defineComponent({
  name: 'BaseLayout',
  components: { Header },
});
</script>
