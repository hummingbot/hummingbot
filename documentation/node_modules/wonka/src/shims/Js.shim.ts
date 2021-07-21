export type Exn_t = Error;
export type Internal_meth<_T, R> = () => R;

export type talkbackT = 0 | 1;

export type signalT<a> =
  | ({ tag: 0 } & [(talkback: talkbackT) => void])
  | ({ tag: 1 } & [a])
  | 0;

export interface observableSubscriptionT {
  unsubscribe(): void;
}

export interface observableObserverT<a> {
  next(value: a): void;
  error(error: any): void;
  complete(): void;
}

export interface observableT<a> {
  subscribe(observer: observableObserverT<a>): observableSubscriptionT;
}

interface Callbag<I, O> {
  (t: 0, d: Callbag<O, I>): void;
  (t: 1, d: I): void;
  (t: 2, d?: any): void;
}

export type callbagT<a> = Callbag<void, a>;
