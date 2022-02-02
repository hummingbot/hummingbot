<template>
  <q-layout view="lHh Lpr lFf" class="flex column">
    <q-page-container class="q-py-lg q-px-xl flex self-center full-width page">
      <Header />
      <q-page>
        <slot />
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Header from '../components/Header/Header.vue';

export default defineComponent({
  components: { Header },
});
</script>

<style lang="scss" scoped>
.page {
  max-width: 1440px;
}
</style>
