<template>
  <div class="column">
    <Steps />
    <Form />
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Steps from './components/Stepper/Steps.vue';
import Form from './Forms/Form.vue';

export default defineComponent({
  components: { Steps, Form },
});
</script>
