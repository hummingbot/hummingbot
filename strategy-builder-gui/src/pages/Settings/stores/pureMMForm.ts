import { StrategyName } from 'src/stores/strategies';
import { ref } from 'vue';

import { $Form, BtnToggleType } from './form.types';

export const $pureMMForm: $Form = {
  bid_spread: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  ask_spread: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_refresh_time: {
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
  order_amount: {
    value: ref(''),
    properties: {
      placeholder: '0.00',
      rightText: 'BTC',
    },
  },
  ping_pong_enabled: {
    value: ref(false),
  },
  order_levels: {
    value: ref(0),
    properties: {
      min: 0,
      max: 10,
      step: 1,
    },
  },
  order_level_amount: {
    value: ref(0),
    properties: {
      min: 0,
      max: 10,
      step: 1,
    },
  },
  order_level_spread: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  inventory_skew_enabled: {
    value: ref(false),
  },
  inventory_target_base_pctCounter: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  inventory_target_base_pctToggle: {
    value: ref(false),
  },
  inventory_range_multiplier: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  inventory_price: {
    value: ref(''),
    properties: {
      placeholder: 'Input Price',
      rightText: '',
    },
  },
  filled_order_delay: {
    value: ref(0),
    properties: {
      min: 1,
      max: 10,
      step: 1,
    },
  },
  hanging_orders_enabled: {
    value: ref(false),
  },
  hanging_orders_cancel_pct: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  minimum_spread: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  order_refresh_tolerance_pct: {
    value: ref(0),
    properties: {
      min: 0,
      max: 1,
      step: 0.1,
    },
  },
  price_ceiling: {
    value: ref(''),
    properties: {
      placeholder: 'Price ceiling',
      rightText: '',
    },
  },
  price_floor: {
    value: ref(''),
    properties: {
      placeholder: 'Price floor',
      rightText: '',
    },
  },
  orderOptimisation: {
    value: ref(false),
  },
  ask_order_optimization_depth: {
    value: ref(''),
    properties: {
      placeholder: 'Ask order',
      rightText: '',
    },
  },
  bid_order_optimization_depth: {
    value: ref(''),
    properties: {
      placeholder: 'Bid order',
      rightText: '',
    },
  },
  add_transaction_costs: {
    value: ref(false),
  },
  price_source: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose source',
    },
  },
  price_type: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose type',
    },
  },
  price_source_exchange: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose exchange',
    },
  },
  price_source_market: {
    value: ref(''),
    properties: {
      options: ['1', '2', '3', '4', '5'],
      labelText: 'Choose pair',
    },
  },
  take_if_crossed: {
    value: ref(false),
  },
  price_source_custom_api: {
    value: ref(''),
    properties: {
      placeholder: 'Pricing API url',
      rightText: '',
    },
  },

  custom_api_update_interval: {
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
  max_order_age: {
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
