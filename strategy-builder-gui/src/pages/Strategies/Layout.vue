<template>
  <BaseLayout>
    <Strategies />
  </BaseLayout>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Strategies from './components/Index.vue';

export default defineComponent({
  components: { Strategies },
});
</script>

<style></style>
