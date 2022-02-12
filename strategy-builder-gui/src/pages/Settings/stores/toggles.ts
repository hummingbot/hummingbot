import { Ref, ref } from 'vue';

type Toggle = {
  [key: string]: {
    model: Ref<boolean>;
    name: string;
  };
};

export const toggles: Toggle = {
  pingPong: {
    name: 'pingPong',
    model: ref(false),
  },
};
