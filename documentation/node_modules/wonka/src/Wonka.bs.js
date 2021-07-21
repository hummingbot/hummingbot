

import * as WonkaJs from "./web/WonkaJs.bs.js";
import * as Wonka_sinks from "./Wonka_sinks.bs.js";
import * as Wonka_sources from "./Wonka_sources.bs.js";
import * as Wonka_operators from "./Wonka_operators.bs.js";

var Types;

var fromArray = Wonka_sources.fromArray;

var fromList = Wonka_sources.fromList;

var fromValue = Wonka_sources.fromValue;

var make = Wonka_sources.make;

var makeSubject = Wonka_sources.makeSubject;

var empty = Wonka_sources.empty;

var never = Wonka_sources.never;

var buffer = Wonka_operators.buffer;

var combine = Wonka_operators.combine;

var concatMap = Wonka_operators.concatMap;

var concatAll = Wonka_operators.concatAll;

var concat = Wonka_operators.concat;

var filter = Wonka_operators.filter;

var map = Wonka_operators.map;

var mergeMap = Wonka_operators.mergeMap;

var merge = Wonka_operators.merge;

var mergeAll = Wonka_operators.mergeAll;

var flatten = Wonka_operators.flatten;

var onEnd = Wonka_operators.onEnd;

var onPush = Wonka_operators.onPush;

var tap = Wonka_operators.tap;

var onStart = Wonka_operators.onStart;

var sample = Wonka_operators.sample;

var scan = Wonka_operators.scan;

var share = Wonka_operators.share;

var skip = Wonka_operators.skip;

var skipUntil = Wonka_operators.skipUntil;

var skipWhile = Wonka_operators.skipWhile;

var switchMap = Wonka_operators.switchMap;

var switchAll = Wonka_operators.switchAll;

var take = Wonka_operators.take;

var takeLast = Wonka_operators.takeLast;

var takeUntil = Wonka_operators.takeUntil;

var takeWhile = Wonka_operators.takeWhile;

var subscribe = Wonka_sinks.subscribe;

var forEach = Wonka_sinks.forEach;

var publish = Wonka_sinks.publish;

var toArray = Wonka_sinks.toArray;

var fromObservable = WonkaJs.fromObservable;

var toObservable = WonkaJs.toObservable;

var fromCallbag = WonkaJs.fromCallbag;

var toCallbag = WonkaJs.toCallbag;

var debounce = WonkaJs.debounce;

var delay = WonkaJs.delay;

var throttle = WonkaJs.throttle;

var toPromise = WonkaJs.toPromise;

var interval = WonkaJs.interval;

var fromDomEvent = WonkaJs.fromDomEvent;

var fromPromise = WonkaJs.fromPromise;

export {
  Types ,
  fromArray ,
  fromList ,
  fromValue ,
  make ,
  makeSubject ,
  empty ,
  never ,
  buffer ,
  combine ,
  concatMap ,
  concatAll ,
  concat ,
  filter ,
  map ,
  mergeMap ,
  merge ,
  mergeAll ,
  flatten ,
  onEnd ,
  onPush ,
  tap ,
  onStart ,
  sample ,
  scan ,
  share ,
  skip ,
  skipUntil ,
  skipWhile ,
  switchMap ,
  switchAll ,
  take ,
  takeLast ,
  takeUntil ,
  takeWhile ,
  subscribe ,
  forEach ,
  publish ,
  toArray ,
  fromObservable ,
  toObservable ,
  fromCallbag ,
  toCallbag ,
  debounce ,
  delay ,
  throttle ,
  toPromise ,
  interval ,
  fromDomEvent ,
  fromPromise ,
  
}
/* WonkaJs Not a pure module */
