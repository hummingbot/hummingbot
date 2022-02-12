import { Ref, ref } from 'vue';

type Select = {
  [key: string]: {
    model: Ref<string>;
    options: string[];
    labelText: string;
    name: string;
  };
};

export const selects: Select = {
  exchange: {
    model: ref(''),
    options: ['1', '2', '3', '4', '5'],
    labelText: 'Select exchange',
    name: 'exchange',
  },
  market: {
    model: ref(''),
    options: ['1', '2', '3', '4', '5'],
    labelText: 'Select market',
    name: 'market',
  },
};
