<template>
  <BaseLayout>
    <Content />
  </BaseLayout>
</template>

<script lang="ts">
import BaseLayout from 'layouts/BaseLayout.vue';
import { defineComponent } from 'vue';

import Content from './Content.vue';

export default defineComponent({
  components: { Content, BaseLayout },
});
</script>
