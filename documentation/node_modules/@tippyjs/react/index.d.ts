import * as React from 'react';
import {default as tippyCore, Instance, Props, Placement} from 'tippy.js';

type Content = React.ReactNode;

export interface TippyProps extends Partial<Omit<Props, 'content' | 'render'>> {
  children?: React.ReactElement<any>;
  content?: Content;
  visible?: boolean;
  disabled?: boolean;
  className?: string;
  singleton?: SingletonObject;
  reference?: React.RefObject<Element> | Element | null;
  ref?: React.Ref<Element>;
  render?: (
    attrs: {
      'data-placement': Placement;
      'data-reference-hidden'?: string;
      'data-escaped'?: string;
    },
    content?: Content,
  ) => React.ReactNode;
}

declare const Tippy: React.ForwardRefExoticComponent<TippyProps>;
export default Tippy;

export const tippy: typeof tippyCore;

type SingletonHookArgs = {
  instance: Instance;
  content: Content;
  props: Props;
};

type SingletonObject = {
  data?: any;
  hook(args: SingletonHookArgs): void;
};

export interface UseSingletonProps {
  disabled?: boolean;
  overrides?: Array<keyof Props>;
}

export const useSingleton: (
  props?: UseSingletonProps,
) => [SingletonObject, SingletonObject];
