<template>
  <BaseLayout>
    <Strategies />
  </BaseLayout>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import BaseLayout from '../../layouts/BaseLayout.vue';
import Strategies from './components/Index.vue';

export default defineComponent({
  components: { Strategies, BaseLayout },
});
</script>
