<template>
  <div
    class="flex justify-between items-center q-px-xl q-py-md q-mt-md bg-mono-grey-1 rounded-borders"
  >
    <q-btn class="bg-mono-grey-2 text-uppercase text-white q-py-sm" flat>back</q-btn>
    <Steps />
    <q-btn class="bg-main-green-1 text-uppercase text-white q-py-sm" flat>next</q-btn>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import Steps from './Steps.vue';

export default defineComponent({
  components: { Steps },
});
</script>

<style></style>
