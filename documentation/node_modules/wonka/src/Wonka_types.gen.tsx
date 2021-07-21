/* TypeScript file generated from Wonka_types.re by genType. */
/* eslint-disable import/first */


import {signalT as $$signalT} from './shims/Js.shim';

import {talkbackT as $$talkbackT} from './shims/Js.shim';

// tslint:disable-next-line:interface-over-type-literal
export type talkbackT = $$talkbackT;

// tslint:disable-next-line:interface-over-type-literal
export type signalT<a> = $$signalT<a>;

// tslint:disable-next-line:interface-over-type-literal
export type sinkT<a> = (_1:signalT<a>) => void;

// tslint:disable-next-line:interface-over-type-literal
export type sourceT<a> = (_1:sinkT<a>) => void;

// tslint:disable-next-line:interface-over-type-literal
export type operatorT<a,b> = (_1:sourceT<a>) => sourceT<b>;

// tslint:disable-next-line:interface-over-type-literal
export type teardownT = () => void;

// tslint:disable-next-line:interface-over-type-literal
export type subscriptionT = { readonly unsubscribe: () => void };

// tslint:disable-next-line:interface-over-type-literal
export type observerT<a> = { readonly next: (_1:a) => void; readonly complete: () => void };

// tslint:disable-next-line:interface-over-type-literal
export type subjectT<a> = {
  readonly source: sourceT<a>; 
  readonly next: (_1:a) => void; 
  readonly complete: () => void
};
