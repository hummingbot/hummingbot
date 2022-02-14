import { Ref, ref } from 'vue';

interface Counter {
  value: Ref<number>;
  properties: {
    min: number;
    max: number;
    step: number;
  };
}

interface Select {
  value: Ref<string>;
  properties: {
    options: string[];
    labelText: string;
  };
}

interface Input {
  value: Ref<string>;
  properties: {
    placeholder?: string;
    rightText?: string;
  };
}

interface Toggle {
  value: Ref<boolean>;
}

interface $SettingsForm {
  [key: string]: Counter | Select | Toggle | Input;
}

export const $settingsForm: $SettingsForm = {
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
  orderAmount: {
    value: ref(''),
    properties: {
      placeholder: '0.00',
      rightText: 'BTC',
    },
  },
  pingPong: {
    value: ref(false),
  },
};
