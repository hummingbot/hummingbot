<template>
  <div class="column">
    <Steps :in-progress-step="2" />
    <Form />
    <Pager />
  </div>
</template>

<script>
import { defineComponent } from 'vue';

import Pager from './components/Pager/Index.vue';
import Steps from './components/Stepper/Steps.vue';
import Form from './Form.vue';

export default defineComponent({
  components: { Steps, Pager, Form },
});
</script>
