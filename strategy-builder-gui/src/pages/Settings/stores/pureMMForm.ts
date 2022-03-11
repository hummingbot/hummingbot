import { StrategyName } from 'src/stores/strategies';
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
  inventoryTargetBase: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
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
  hangingOrdersCancel: {
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
  orderRefreshTolerance: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  priceCelling: {
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
  priceSourceCustomApi: {
    value: ref(''),
    properties: {
      placeholder: 'Pricing API url',
      rightText: '',
    },
  },

  customApiUpdateInterval: {
    value: ref(0),
    properties: {
      min: 1,
      max: 10,
      step: 1,
    },
  },

  order_1_Toggle: {
    value: ref(BtnToggleType.Buy),
  },

  order_1_FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_1_SecondCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },

  order_2_Toggle: {
    value: ref(BtnToggleType.Buy),
  },
  order_2_FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_2_SecondCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_3_Toggle: {
    value: ref(BtnToggleType.Buy),
  },
  order_3_FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_3_SecondCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_4_Toggle: {
    value: ref(BtnToggleType.Buy),
  },
  order_4_FirstCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_4_SecondCounter: {
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
    value: ref(StrategyName.PureMarketMaking),
    properties: {
      placeholder: 'Title',
      rightText: '.yml',
    },
  },
};
