import { Ref, ref } from 'vue';

interface Form {
  counters?: {
    [key: string]: Ref<{
      min: number;
      max: number;
      modelValue: number;
      stepValue: number;
    }>;
  };
  inputs?: {
    [key: string]: Ref<{
      placeholder?: string;
      rightText?: string;
      modelValue: string;
    }>;
  };
  selects?: {
    [key: string]: Ref<{
      modelValue: string;
      options: string[];
      labelText: string;
    }>;
  };
  toggles?: {
    [key: string]: Ref<{
      modelValue: boolean;
    }>;
  };
}

export const $settingsForm: Form = {
  counters: {
    bidSpread: ref({
      min: 0,
      max: 1,
      modelValue: ref(0),
      stepValue: 0.1,
    }),
    askSpread: ref({
      min: 0,
      max: 1,
      modelValue: ref(0),
      stepValue: 0.1,
    }),
    orderRefreshTime: ref({
      min: 0,
      max: 10,
      modelValue: ref(0),
      stepValue: 1,
    }),
  },
  selects: {
    exchange: ref({
      modelValue: ref(''),
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Select exchange',
    }),
    market: ref({
      modelValue: ref(''),
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Select market',
    }),
  },
  inputs: {
    orderAmount: ref({
      placeholder: '0.00',
      rightText: 'BTC',
      modelValue: ref(''),
    }),
  },
  toggles: {
    pingPong: ref({
      modelValue: ref(false),
    }),
  },
};
