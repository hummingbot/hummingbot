<template>
  <q-layout view="lHh Lpr lFf" class="flex column">
    <Header class="q-pt-lg q-px-xl col-auto self-center full-width page" />
    <q-page-container>
      <q-page class="q-pb-lg q-px-xl flex column self-center full-width page">
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
