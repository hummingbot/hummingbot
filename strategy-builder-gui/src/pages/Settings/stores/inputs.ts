import { Ref, ref } from 'vue';

export enum InputType {
  Text,
  Number,
}

type Input = {
  [key: string]: {
    type: InputType;
    name: string;
    placeholder?: string;
    rightText?: string;
    model: Ref<unknown>;
  };
};

export const inputs: Input = {
  orderAmount: {
    type: InputType.Number,
    name: 'orderAmount',
    placeholder: '0.00',
    rightText: 'BTC',
    model: ref(null),
  },
  test: {
    type: InputType.Text,
    name: 'test',
    placeholder: 'ewqeee',
    rightText: 'errRR',
    model: ref(''),
  },
};
