import { StrategyName } from 'src/composables/useStrategies';
import { Ref } from 'vue';

export enum BtnToggleType {
  Sell = 'Sell',
  Buy = 'Buy',
}

export interface Counter {
  value: Ref<number>;
  properties: {
    min: number;
    max: number;
    step: number;
  };
}
export interface Select {
  value: Ref<string>;
  properties: {
    options: string[];
    labelText: string;
  };
}

export interface Input {
  value: Ref<string>;
  properties: {
    placeholder?: string;
    rightText?: string;
  };
}
export interface Toggle {
  value: Ref<boolean>;
}

export interface BtnToggle {
  value: Ref<BtnToggleType>;
}

export interface $Form {
  [key: string]: Counter | Select | Toggle | Input | BtnToggle;
}

export type $SettingsForm = {
  [key in `${StrategyName}`]: $Form;
};
