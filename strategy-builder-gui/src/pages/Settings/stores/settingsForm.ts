import { Ref, ref } from 'vue';

interface Form {
  counters?: {
    [key: string]: {
      value: Ref<number>;
      properties: {
        min: number;
        max: number;
        step: number;
      };
    };
  };
  inputs?: {
    [key: string]: {
      value: Ref<string>;
      properties: {
        placeholder?: string;
        rightText?: string;
      };
    };
  };
  selects?: {
    [key: string]: {
      value: Ref<string>;
      properties: {
        options: string[];
        labelText: string;
      };
    };
  };
  toggles?: {
    [key: string]: {
      value: Ref<boolean>;
    };
  };
}

export const $settingsForm: Form = {
  counters: {
    bidSpread: {
      value: ref(0),
      properties: {
        min: 0,
        max: 1,
        step: 0.1,
      },
    },
    askSpread: {
      value: ref(0),
      properties: {
        min: 0,
        max: 1,
        step: 0.1,
      },
    },
    orderRefreshTime: {
      value: ref(0),
      properties: {
        min: 0,
        max: 10,
        step: 1,
      },
    },
  },
  selects: {
    exchange: {
      value: ref(''),
      properties: {
        options: ['1', '2', '3', '4', '5'],
        labelText: 'Select exchange',
      },
    },
    market: {
      value: ref(''),
      properties: {
        options: ['1', '2', '3', '4', '5'],
        labelText: 'Select market',
      },
    },
  },
  inputs: {
    orderAmount: {
      value: ref(''),
      properties: {
        placeholder: '0.00',
        rightText: 'BTC',
      },
    },
  },
  toggles: {
    pingPong: {
      value: ref(false),
    },
  },
};
