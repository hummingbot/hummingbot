/* TypeScript file generated from Wonka_operators.re by genType. */
/* eslint-disable import/first */


// tslint:disable-next-line:no-var-requires
const Curry = require('bs-platform/lib/es6/curry.js');

// tslint:disable-next-line:no-var-requires
const Wonka_operatorsBS = require('./Wonka_operators.bs');

import {operatorT as Wonka_types_operatorT} from './Wonka_types.gen';

import {sourceT as Wonka_types_sourceT} from './Wonka_types.gen';

export const buffer: <a,b>(notifier:Wonka_types_sourceT<a>) => Wonka_types_operatorT<b,b[]> = Wonka_operatorsBS.buffer;

export const combine: <a,b>(sourceA:Wonka_types_sourceT<a>, sourceB:Wonka_types_sourceT<b>) => Wonka_types_sourceT<[a, b]> = function <a,b>(Arg1: any, Arg2: any) {
  const result = Curry._2(Wonka_operatorsBS.combine, Arg1, Arg2);
  return result
};

export const concatMap: <a,b>(f:((_1:a) => Wonka_types_sourceT<b>)) => Wonka_types_operatorT<a,b> = Wonka_operatorsBS.concatMap;

export const concatAll: <a>(source:Wonka_types_sourceT<Wonka_types_sourceT<a>>) => Wonka_types_sourceT<a> = Wonka_operatorsBS.concatAll;

export const concat: <a>(sources:Wonka_types_sourceT<a>[]) => Wonka_types_sourceT<a> = Wonka_operatorsBS.concat;

export const filter: <a>(f:((_1:a) => boolean)) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.filter;

export const map: <a,b>(f:((_1:a) => b)) => Wonka_types_operatorT<a,b> = Wonka_operatorsBS.map;

export const mergeMap: <a,b>(f:((_1:a) => Wonka_types_sourceT<b>)) => Wonka_types_operatorT<a,b> = Wonka_operatorsBS.mergeMap;

export const merge: <a>(sources:Wonka_types_sourceT<a>[]) => Wonka_types_sourceT<a> = Wonka_operatorsBS.merge;

export const mergeAll: <a>(source:Wonka_types_sourceT<Wonka_types_sourceT<a>>) => Wonka_types_sourceT<a> = Wonka_operatorsBS.mergeAll;

export const flatten: <T1>(_1:Wonka_types_sourceT<Wonka_types_sourceT<T1>>) => Wonka_types_sourceT<T1> = Wonka_operatorsBS.flatten;

export const onEnd: <a>(f:(() => void)) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.onEnd;

export const onPush: <a>(f:((_1:a) => void)) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.onPush;

export const tap: <T1>(_1:((_1:T1) => void)) => Wonka_types_operatorT<T1,T1> = Wonka_operatorsBS.tap;

export const onStart: <a>(f:(() => void)) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.onStart;

export const sample: <a,b>(notifier:Wonka_types_sourceT<a>) => Wonka_types_operatorT<b,b> = Wonka_operatorsBS.sample;

export const scan: <a,acc>(f:((_1:acc, _2:a) => acc), seed:acc) => Wonka_types_operatorT<a,acc> = function <a,acc>(Arg1: any, Arg2: any) {
  const result = Curry._2(Wonka_operatorsBS.scan, Arg1, Arg2);
  return result
};

export const share: <a>(source:Wonka_types_sourceT<a>) => Wonka_types_sourceT<a> = Wonka_operatorsBS.share;

export const skip: <a>(wait:number) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.skip;

export const skipUntil: <a,b>(notifier:Wonka_types_sourceT<a>) => Wonka_types_operatorT<b,b> = Wonka_operatorsBS.skipUntil;

export const skipWhile: <a>(f:((_1:a) => boolean)) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.skipWhile;

export const switchMap: <a,b>(f:((_1:a) => Wonka_types_sourceT<b>)) => Wonka_types_operatorT<a,b> = Wonka_operatorsBS.switchMap;

export const switchAll: <a>(source:Wonka_types_sourceT<Wonka_types_sourceT<a>>) => Wonka_types_sourceT<a> = Wonka_operatorsBS.switchAll;

export const take: <a>(max:number) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.take;

export const takeLast: <a>(max:number) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.takeLast;

export const takeUntil: <a,b>(notifier:Wonka_types_sourceT<a>) => Wonka_types_operatorT<b,b> = Wonka_operatorsBS.takeUntil;

export const takeWhile: <a>(f:((_1:a) => boolean)) => Wonka_types_operatorT<a,a> = Wonka_operatorsBS.takeWhile;
