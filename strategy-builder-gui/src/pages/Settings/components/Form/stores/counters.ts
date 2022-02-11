import { Ref, ref } from 'vue';

export enum CounterTypes {
  Percentage,
  Seconds,
  CountInt,
  FloatCount,
}

type Counter = {
  [key: string]: {
    type: CounterTypes;
    name: string;
    min: number;
    max: number;
    model: Ref<number>;
    stepValue: number;
  };
};

export const counters: Counter = {
  bidSpread: {
    type: CounterTypes.Percentage,
    name: 'bidSpread',
    min: 0,
    max: 1,
    model: ref(0),
    stepValue: 0.1,
  },
};
