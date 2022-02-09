<template>
  <div class="row q-gutter-sm">
    <div class="col-12 col-md">
      <Step />
    </div>
    <div class="col-12 col-md">
      <Step />
    </div>
    <div class="col-12 col-md">
      <Step />
    </div>
  </div>
</template>

<script>
import { defineComponent } from 'vue';

import Step from './Step.vue';

export default defineComponent({
  components: { Step },
});
</script>

<style></style>
