import { Ref, ref } from 'vue';

export enum OrderStatus {
  Sell = 'Buy',
  Buy = 'Sell',
}

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

interface Order {
  value: Ref<OrderStatus>;
  properties: {
    title: string;
  };
}
interface Toggle {
  value: Ref<boolean>;
}

interface $SettingsForm {
  [key: string]: Counter | Select | Toggle | Input | Order;
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
  orderLevels: {
    value: ref(0),
    properties: {
      min: 0,
      max: 10,
      step: 1,
    },
  },
  orderLevelAmount: {
    value: ref(0),
    properties: {
      min: 0,
      max: 10,
      step: 1,
    },
  },
  orderLevelSpread: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  inventorySkew: {
    value: ref(false),
  },
  inventoryTargetBaseCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  inventoryTargetBaseToggle: {
    value: ref(false),
  },
  inventoryRangeMultiplier: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  inventoryPrice: {
    value: ref(''),
    properties: {
      placeholder: 'Input Price',
      rightText: '',
    },
  },
  filledOrderDelay: {
    value: ref(0),
    properties: {
      min: 1,
      max: 10,
      step: 1,
    },
  },
  hangingOrders: {
    value: ref(false),
  },
  hangingOrderCancel: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  minimumSpread: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  orderRefreshTollerance: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  priceCeiling: {
    value: ref(''),
    properties: {
      placeholder: 'Price ceiling',
      rightText: '',
    },
  },
  priceFloor: {
    value: ref(''),
    properties: {
      placeholder: 'Price floor',
      rightText: '',
    },
  },
  orderOptimisation: {
    value: ref(false),
  },
  askOrderOptimizationDepth: {
    value: ref(''),
    properties: {
      placeholder: 'Ask order',
      rightText: '',
    },
  },
  bidOrderOptimizationDepth: {
    value: ref(''),
    properties: {
      placeholder: 'Bid order',
      rightText: '',
    },
  },
  addTransactionCosts: {
    value: ref(false),
  },
  priceSource: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose source',
    },
  },
  priceType: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose type',
    },
  },
  priceSourceExchange: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose exchange',
    },
  },
  priceSourceMarket: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose pair',
    },
  },
  takeIfCrossed: {
    value: ref(false),
  },
  priceSourceCustomAPI: {
    value: ref(''),
    properties: {
      placeholder: 'Pricing API url',
      rightText: '',
    },
  },

  order1: {
    value: ref(OrderStatus.Sell),
    properties: {
      title: 'Order 1',
    },
  },
  order1FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order1SecondCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order2: {
    value: ref(OrderStatus.Sell),
    properties: {
      title: 'Order 2',
    },
  },
  order2FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order2SecondCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order3: {
    value: ref(OrderStatus.Sell),
    properties: {
      title: 'Order 3',
    },
  },
  order3FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order3SecondCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order4: {
    value: ref(OrderStatus.Sell),
    properties: {
      title: 'Order 4',
    },
  },
  order4FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order4SecondCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  maxOrderAge: {
    value: ref(0),
    properties: {
      min: 1,
      max: 10,
      step: 1,
    },
  },
};
