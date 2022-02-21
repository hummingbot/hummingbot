import { Ref } from 'vue';

export enum FormList {
  PureMarketMaking = 'pure-market-making',
}

export enum BtnToggleType {
  Sell = 'Buy',
  Buy = 'Sell',
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

export interface $SettingsForm {
  [key: string]: $Form;
}
