<template>
  <q-layout view="lHh Lpr lFf">
    <q-page-container class="flex">
      <q-page class="q-py-lg q-px-xl flex column self-center full-width page">
        <Header class="col-auto" />
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
