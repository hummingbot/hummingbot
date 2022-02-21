import { ref } from 'vue';

import { $Form, BtnToggleType } from './form.types';

export const $pureMMForm: $Form = {
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

  order1Toggle: {
    value: ref(BtnToggleType.Buy),
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

  order2Toggle: {
    value: ref(BtnToggleType.Buy),
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
  order3Toggle: {
    value: ref(BtnToggleType.Buy),
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
  order4Toggle: {
    value: ref(BtnToggleType.Buy),
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
  fileName: {
    value: ref(''),
    properties: {
      placeholder: 'Title',
      rightText: '.yml',
    },
  },
};
