<template>
  <div class="column">
    <Steps :in-progress-step="2" />
    <Form />
  </div>
</template>

<script>
import { defineComponent } from 'vue';

import Steps from './components/Stepper/Steps.vue';
import Form from './Form.vue';

export default defineComponent({
  components: { Steps, Form },
});
</script>
