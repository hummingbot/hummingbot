/* TypeScript file generated from Wonka_sources.re by genType. */
/* eslint-disable import/first */


// tslint:disable-next-line:no-var-requires
const Wonka_sourcesBS = require('./Wonka_sources.bs');

import {list} from '../src/shims/ReasonPervasives.shim';

import {observerT as Wonka_types_observerT} from './Wonka_types.gen';

import {sinkT as Wonka_types_sinkT} from './Wonka_types.gen';

import {sourceT as Wonka_types_sourceT} from './Wonka_types.gen';

import {subjectT as Wonka_types_subjectT} from './Wonka_types.gen';

import {teardownT as Wonka_types_teardownT} from './Wonka_types.gen';

export const fromArray: <a>(arr:a[]) => Wonka_types_sourceT<a> = Wonka_sourcesBS.fromArray;

export const fromList: <a>(ls:list<a>) => Wonka_types_sourceT<a> = Wonka_sourcesBS.fromList;

export const fromValue: <a>(x:a) => Wonka_types_sourceT<a> = Wonka_sourcesBS.fromValue;

export const make: <a>(f:((_1:Wonka_types_observerT<a>) => Wonka_types_teardownT)) => Wonka_types_sourceT<a> = Wonka_sourcesBS.make;

export const makeSubject: <a>() => Wonka_types_subjectT<a> = Wonka_sourcesBS.makeSubject;

export const empty: <a>(sink:Wonka_types_sinkT<a>) => void = Wonka_sourcesBS.empty;

export const never: <a>(sink:Wonka_types_sinkT<a>) => void = Wonka_sourcesBS.never;
