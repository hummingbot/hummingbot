<template>
  <q-input
    borderless
    class="form-input rounded-borders"
    input-class="q-pl-md q-py-sm"
    :placeholder="placeholder"
    :type="type === InputType.Number ? 'number' : 'text'"
    :model-value="modelValue"
    @update:model-value="(value) => $emit('update:modelValue', value)"
  >
    <template #append>
      <div class="text-white text-h6 full-height flex items-center q-pr-md">{{ rightText }}</div>
    </template>
  </q-input>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

export enum InputType {
  Text,
  Number,
}

export default defineComponent({
  props: {
    type: { type: Number as PropType<InputType>, require: true, default: () => InputType.Number },
    placeholder: { type: String, require: false, default: () => '' },
    rightText: { type: String, require: false, default: () => '' },
    modelValue: { type: String, require: true, default: () => '' },
  },
  emits: ['update:modelValue'],

  setup() {
    return { InputType };
  },
});
</script>

<style lang="scss">
@use 'sass:map';
.form-input {
  border: 1px solid map.get($colors, 'mono-grey-2');
}
.form-input .q-field__append {
  height: 100%;
}
</style>
