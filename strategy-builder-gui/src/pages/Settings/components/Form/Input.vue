<template>
  <q-input
    :model-value="value"
    borderless
    class="form-input rounded-borders"
    input-class="q-pl-md q-py-sm"
    :placeholder="placeholder"
    :type="type === InputType.Number ? 'number' : ''"
    @update:model-value="(value) => onChange(value, name, type === InputType.Number)"
  >
    <template #append>
      <div class="text-white text-h6 full-height flex items-center q-pr-md">{{ rightText }}</div>
    </template>
  </q-input>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';

import { InputType } from '../../stores/inputs';

export default defineComponent({
  props: {
    type: { type: Number as PropType<InputType>, require: true, default: () => InputType.Number },
    placeholder: { type: String, require: false, default: () => '' },
    rightText: { type: String, require: false, default: () => '' },
    name: { type: String, require: false, default: () => '' },
    value: { type: String, require: true, default: () => '' },
    onChange: { type: Function, require: true, default: () => undefined },
  },

  setup() {
    return { InputType };
  },
});
</script>

<style lang="scss">
.form-input {
  border: 1px solid #2f3641;
}
.form-input .q-field__append {
  height: 100%;
}
</style>
