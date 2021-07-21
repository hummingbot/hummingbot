import { __ as block } from 'bs-platform/lib/es6/block';
import { talkbackPlaceholder } from './Wonka_helpers.bs';

import {
  talkbackT,
  signalT
} from '../Wonka_types.gen';

type talkbackCb = (tb: talkbackT) => void;

export const pull = (0 as any as talkbackT);
export const close = (1 as any as talkbackT);

export const start = <a>(tb: talkbackCb): signalT<a> => block(0, [tb]) as any;
export const push = <a>(x: a): signalT<a> => block(1, [x]) as any;
export const end = <a>(): signalT<a> => 0 as any;

export const isStart = <a>(s: signalT<a>) =>
  typeof s !== 'number' && (s as any).tag === 0;
export const isPush = <a>(s: signalT<a>) =>
  typeof s !== 'number' && (s as any).tag === 1;
export const isEnd = <a>(s: signalT<a>) =>
  typeof s === 'number' && (s as any) === 0;

export const unboxPush = <a>(s: signalT<a>): a | null =>
  isPush(s) ? (s as any)[0] : null;
export const unboxStart = <a>(s: signalT<a>): talkbackCb =>
  isStart(s) ? (s as any)[0] : (talkbackPlaceholder as any);
