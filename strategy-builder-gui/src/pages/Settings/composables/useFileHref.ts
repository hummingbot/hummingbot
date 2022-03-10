import { computed, ComputedRef } from 'vue';

export const useFileHref = (values: ComputedRef) => {
  const valuesObj = { ...values.value };

  delete valuesObj.fileName;

  return computed(
    () =>
      `data:application/octet-stream,${JSON.stringify(valuesObj)
        .replace(/,/g, '\n')
        .replace(/[{}]/g, '')
        .replace(/"/g, ' ')}`,
  );
};
