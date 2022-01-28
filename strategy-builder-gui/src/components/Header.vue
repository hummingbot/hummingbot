<template>
  <div class="row flex items-center q-mb-lg" style="height: 56px">
    <div class="col"> <img src="~assets/header-logo.svg" style="cursor: pointer" /> </div>
    <div class="col flex justify-end">
      <q-btn color="mono-grey-1" class="q-py-md q-px-lg text-h6" @click="onClickUpload()"
        >UPLOAD STRATEGY</q-btn
      >
    </div>
  </div>
</template>

<script lang="ts">
export default {
  setup() {
    function onClickUpload() {
      // eslint-disable-next-line no-console
      console.log('upload click');
    }

    return { onClickUpload };
  },
};
</script>

<style></style>
