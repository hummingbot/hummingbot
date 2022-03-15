import { StrategyName } from 'src/stores/strategies';
import { ref } from 'vue';

import { $Form, BtnToggleType, FileMap, OrderType } from './form.types';

export const defaultOrder: OrderType = {
  value: ref(BtnToggleType.Sell),
  orderAmount: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  orderLevelParam: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
};

export const pureMMFormFileFieldsMap: FileMap = {
  bidSpread: 'bid_spread',
  askSpread: 'ask_spread',
  orderRefreshTime: 'order_refresh_time',
  exchange: 'exchange',
  market: 'market',
  orderAmount: 'order_amount',
  pingPong: 'ping_pong_enabled',
  orderLevels: 'order_levels',
  orderLevelAmount: 'orderLevelAmount',
  orderLevelSpread: 'orderLevelSpread',
  inventorySkew: 'inventory_skew_enabled',
  inventoryTargetBase: 'inventory_target_base_pct',
  inventoryRangeMultiplier: 'inventory_range_multiplier',
  inventoryPrice: 'inventory_price',
  filledOrderDelay: 'filled_order_delay',
  hangingOrders: 'hanging_orders_enabled',
  hangingOrdersCancel: 'hanging_orders_cancel_pct',
  minimumSpread: 'minimum_spread',
  orderRefreshTolerance: 'order_refresh_tolerance_pct',
  priceCelling: 'price_ceiling',
  priceFloor: 'price_floor',
  orderOptimization: 'order_optimization_enabled',
  askOrderOptimizationDepth: 'ask_order_optimization_depth',
  bidOrderOptimizationDepth: 'bid_order_optimization_depth',
  addTransactionCosts: 'add_transaction_costs',
  priceSource: 'price_source',
  priceType: 'price_type',
  priceSourceExchange: 'price_source_exchange',
  priceSourceMarket: 'price_source_market',
  takeIfCrossed: 'take_if_crossed',
  priceSourceCustomApi: 'price_source_custom_api',
  customApiUpdateInterval: 'custom_api_update_interval',
  maxOrderAge: 'max_order_age',
};

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
  orderOptimization: {
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

  orders: {
    value: ref(0),
    list: [],
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
