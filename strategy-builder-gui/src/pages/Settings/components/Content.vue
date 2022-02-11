<template>
  <div class="column">
    <Steps :in-progress-step="2" />
    <Form />
  </div>
</template>

<script>
import { defineComponent } from 'vue';

import Form from './Form/Form.vue';
import Steps from './Stepper/Steps.vue';

export default defineComponent({
  components: { Steps, Form },
});
</script>
