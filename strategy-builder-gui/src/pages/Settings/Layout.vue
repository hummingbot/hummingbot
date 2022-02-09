<template>
  <BaseLayout>
    <Settings />
  </BaseLayout>
</template>

<script lang="ts">
import BaseLayout from 'layouts/BaseLayout.vue';
import { defineComponent } from 'vue';

import Settings from './components/Content.vue';

export default defineComponent({
  components: { Settings, BaseLayout },
});
</script>
