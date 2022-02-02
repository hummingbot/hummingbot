<template #header>
  <q-toolbar class="row flex items-center q-mb-lg q-px-none">
    <div class="col">
      <router-link class="q-px-none q-py-none" clickable to="/">
        <q-img
          :src="require('./assets/header-logo.svg')"
          fit="contain"
          no-transition
          class="logo"
        />
      </router-link>
    </div>
    <div class="col flex justify-end">
      <q-btn color="mono-grey-1" class="text-h6 text-uppercase btn" @click="onClickUpload()">
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
.btn {
  padding: 12px 24px;
  font-size: 12px;
}

.logo {
  max-width: 56px;
}
</style>
