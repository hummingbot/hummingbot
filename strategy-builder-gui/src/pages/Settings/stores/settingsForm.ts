import { Ref, ref } from 'vue';

interface Form {
  counters?: {
    [key: string]: {
      modelValue: Ref<number>;
      properties: {
        min: number;
        max: number;
        stepValue: number;
      };
    };
  };
  inputs?: {
    [key: string]: {
      modelValue: Ref<string>;
      properties: {
        placeholder?: string;
        rightText?: string;
      };
    };
  };
  selects?: {
    [key: string]: {
      modelValue: Ref<string>;
      properties: {
        options: string[];
        labelText: string;
      };
    };
  };
  toggles?: {
    [key: string]: {
      modelValue: Ref<boolean>;
    };
  };
}

export const $settingsForm: Form = {
  counters: {
    bidSpread: {
      modelValue: ref(0),
      properties: {
        min: 0,
        max: 1,
        stepValue: 0.1,
      },
    },
    askSpread: {
      modelValue: ref(0),
      properties: {
        min: 0,
        max: 1,
        stepValue: 0.1,
      },
    },
    orderRefreshTime: {
      modelValue: ref(0),
      properties: {
        min: 0,
        max: 10,
        stepValue: 1,
      },
    },
  },
  selects: {
    exchange: {
      modelValue: ref(''),
      properties: {
        options: ['1', '2', '3', '4', '5'],
        labelText: 'Select exchange',
      },
    },
    market: {
      modelValue: ref(''),
      properties: {
        options: ['1', '2', '3', '4', '5'],
        labelText: 'Select market',
      },
    },
  },
  inputs: {
    orderAmount: {
      modelValue: ref(''),
      properties: {
        placeholder: '0.00',
        rightText: 'BTC',
      },
    },
  },
  toggles: {
    pingPong: {
      modelValue: ref(false),
    },
  },
};
