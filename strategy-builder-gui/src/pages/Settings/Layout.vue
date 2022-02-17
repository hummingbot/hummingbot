<template>
  <BaseLayout class="settings-page">
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
<style lang="scss" scoped>
.settings-page {
  max-width: 878px;
  width: 100%;
  margin: 0 auto;
}
</style>
