<template>
  <q-select
    class="form-select col"
    :name="name"
    borderless
    :options="exchanges"
    :display-value="modelValue"
    rounded
    :label="labelText"
    :model-value="modelValue"
    label-color="mono-grey-3"
    :dropdown-icon="`img:${require('../../assets/select-btn.svg')}`"
    popup-content-class="bg-mono-grey-2 q-px-md q-py-md"
    options-selected-class="bg-mono-grey-3 rounded-borders"
    @update:model-value="(value) => onChange(value, name)"
  />
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue';

export default defineComponent({
  props: {
    modelValue: { type: String, require: true, default: () => '' },
    options: { type: Array, require: true, default: () => ['1', '2'] },
    labelText: { type: String, require: true, default: () => 'Select...' },
    name: { type: String, require: true, default: () => '' },
    onChange: { type: Function, require: true, default: () => undefined },
  },
  setup(props) {
    const exchanges = ref(props.options);

    return { exchanges };
  },
});
</script>

<style lang="scss">
@use 'sass:map';

.form-select {
  max-width: 170px !important;
  max-height: 36px !important;
}

.form-select span {
  font-weight: 600;
  font-size: 14px;
  color: map.get($colors, 'mono-grey-6');
}

.form-select .q-field__control {
  align-items: center;
}

.form-select .q-field__append.q-field__marginal {
  padding-left: 12px;
}

.form-select .q-field__control .q-field__control-container {
  padding-top: 0 !important;
}

.form-select.q-field--float .q-field__control .q-field__control-container {
  padding-top: 8px !important;
}

.form-select.q-field--float .q-field__label {
  display: none;
}

.form-select.q-field--float.q-field--focused .q-field__label {
  display: block;
}

.form-select .q-field__native {
  justify-content: end;
}

.form-select .q-field__label {
  top: 0;
  width: 100%;
  text-align: right;
}

.form-select.q-field--float .q-field__label {
  top: -5px;
  left: 24%;
}
</style>
