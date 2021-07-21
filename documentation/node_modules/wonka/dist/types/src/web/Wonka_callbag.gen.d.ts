import { callbagT as $$callbagT } from '../shims/Js.shim';
import { sourceT as Wonka_types_sourceT } from '../../src/Wonka_types.gen';
export declare type callbagSignal = 0 | 1 | 2;
export declare abstract class callbagData<a> {
    protected opaque: a;
}
export declare type callbagTalkback = (_1: callbagSignal) => void;
export declare type callbagT<a> = $$callbagT<a>;
export declare const fromCallbag: <a>(callbag: callbagT<a>) => Wonka_types_sourceT<a>;
export declare const toCallbag: <a>(source: Wonka_types_sourceT<a>) => callbagT<a>;
