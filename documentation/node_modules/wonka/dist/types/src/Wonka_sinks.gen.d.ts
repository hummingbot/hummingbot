import { sourceT as Wonka_types_sourceT } from './Wonka_types.gen';
import { subscriptionT as Wonka_types_subscriptionT } from './Wonka_types.gen';
export declare type subscribeConsumerT<a> = (_1: Wonka_types_sourceT<a>) => Wonka_types_subscriptionT;
export declare type forEachConsumerT<a> = (_1: Wonka_types_sourceT<a>) => void;
export declare const subscribe: <a>(f: ((_1: a) => void)) => subscribeConsumerT<a>;
export declare const forEach: <a>(f: ((_1: a) => void)) => forEachConsumerT<a>;
export declare const publish: <a>(source: Wonka_types_sourceT<a>) => Wonka_types_subscriptionT;
export declare const toArray: <a>(source: Wonka_types_sourceT<a>) => a[];
