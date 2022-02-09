<template>
  <div><Steps :in-progress-step="2" /></div>
</template>

<script>
import { defineComponent } from 'vue';

import Steps from './Stepper/Steps.vue';

export default defineComponent({
  components: { Steps },
});
</script>
