import { StrategyName } from 'src/stores/strategies';
import { ref } from 'vue';

import { $Form, BtnToggleType, FileMap } from './form.types';

export const defaultOrder = {
  value: BtnToggleType.Sell,
  orderAmount: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  orderLevelParam: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
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
  orders: 'orders',
};

export const $pureMMForm: $Form = {
  bidSpread: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  askSpread: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  orderRefreshTime: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
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
    value: ref(0),
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
      placeholder: '0',
      rightText: '',
    },
  },
  orderLevelAmount: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  orderLevelSpread: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  inventorySkew: {
    value: ref(false),
  },
  inventoryTargetBase: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  inventoryRangeMultiplier: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
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
      placeholder: '0',
      rightText: '',
    },
  },
  hangingOrders: {
    value: ref(false),
  },
  hangingOrdersCancel: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  minimumSpread: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
    },
  },
  orderRefreshTolerance: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
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
      placeholder: '0',
      rightText: '',
    },
  },
  orders: {
    value: ref([]),
  },
  maxOrderAge: {
    value: ref(0),
    properties: {
      placeholder: '0',
      rightText: '',
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
