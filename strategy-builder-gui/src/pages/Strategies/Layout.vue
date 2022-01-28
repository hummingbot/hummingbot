<template>
  <div class="q-py-lg q-px-xl">
    <Header />
    <Strategies />
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Header from '../../components/Header.vue';
import Strategies from './components/Index.vue';

export default defineComponent({
  components: { Strategies, Header },
});
</script>

<style></style>
