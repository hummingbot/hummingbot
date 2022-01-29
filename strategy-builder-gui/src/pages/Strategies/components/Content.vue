<template>
  <div style="gap: 20px" class="flex row">
    <Box class="col" v-bind="{ type: 'strategy' }" />
    <Box class="col" v-bind="{ type: 'exchange' }" />
  </div>
</template>

<script lang="ts">
import Box from './Box.vue';

export default {
  components: { Box },
};
</script>

<style></style>
