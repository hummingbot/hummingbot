/* TypeScript file generated from Wonka_observable.re by genType. */
/* eslint-disable import/first */


// tslint:disable-next-line:no-var-requires
const Wonka_observableBS = require('./Wonka_observable.bs');

import {observableObserverT as $$observableObserverT} from '../shims/Js.shim';

import {observableSubscriptionT as $$observableSubscriptionT} from '../shims/Js.shim';

import {observableT as $$observableT} from '../shims/Js.shim';

import {sourceT as Wonka_types_sourceT} from '../../src/Wonka_types.gen';

// tslint:disable-next-line:interface-over-type-literal
export type observableSubscriptionT = $$observableSubscriptionT;

// tslint:disable-next-line:interface-over-type-literal
export type observableObserverT<a> = $$observableObserverT<a>;

// tslint:disable-next-line:interface-over-type-literal
export type observableT<a> = $$observableT<a>;

export const fromObservable: <a>(input:observableT<a>) => Wonka_types_sourceT<a> = Wonka_observableBS.fromObservable;

export const toObservable: <a>(source:Wonka_types_sourceT<a>) => observableT<a> = Wonka_observableBS.toObservable;
