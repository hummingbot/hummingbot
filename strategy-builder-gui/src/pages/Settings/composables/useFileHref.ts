import { ComputedRef } from 'vue';

export const useFileHref = (values: ComputedRef) =>
  `data:application/octet-stream,${JSON.stringify(values.value)
    .replace(/,/g, '\n')
    .replace(/[{}]/g, '')
    .replace(/"/g, ' ')}`;
