<template #header>
  <q-toolbar class="row flex items-center q-mb-lg q-px-none">
    <div class="col">
      <router-link class="q-px-none q-py-none" to="/">
        <q-img
          :src="require('./header-logo.svg')"
          fit="contain"
          no-transition
          no-spinner
          class="logo"
        />
      </router-link>
    </div>
    <div class="col flex justify-end">
      <q-btn
        color="mono-grey-1"
        size="md"
        padding="md lg"
        class="text-uppercase"
        @click="onClickUpload()"
      >
        Upload strategy
      </q-btn>
    </div>
  </q-toolbar>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  setup() {
    const onClickUpload = () => {
      // eslint-disable-next-line no-console
      console.log('upload click');
    };

    return { onClickUpload };
  },
});
</script>

<style scoped lang="scss">
.logo {
  max-width: 56px;
}
</style>
