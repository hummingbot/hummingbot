import { signalT as $$signalT } from './shims/Js.shim';
import { talkbackT as $$talkbackT } from './shims/Js.shim';
export declare type talkbackT = $$talkbackT;
export declare type signalT<a> = $$signalT<a>;
export declare type sinkT<a> = (_1: signalT<a>) => void;
export declare type sourceT<a> = (_1: sinkT<a>) => void;
export declare type operatorT<a, b> = (_1: sourceT<a>) => sourceT<b>;
export declare type teardownT = () => void;
export declare type subscriptionT = {
    readonly unsubscribe: () => void;
};
export declare type observerT<a> = {
    readonly next: (_1: a) => void;
    readonly complete: () => void;
};
export declare type subjectT<a> = {
    readonly source: sourceT<a>;
    readonly next: (_1: a) => void;
    readonly complete: () => void;
};
