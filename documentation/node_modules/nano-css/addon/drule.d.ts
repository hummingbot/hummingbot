import {CssLikeObject, TDynamicCss} from '../types/common';
import {NanoRenderer} from '../types/nano';

export interface DruleAddon {
    drule: (css: CssLikeObject, block?: string) => TDynamicCss;
}

export function addon(nano: NanoRenderer);
