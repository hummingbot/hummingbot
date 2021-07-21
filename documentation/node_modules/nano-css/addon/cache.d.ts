import {NanoRenderer} from '../types/nano';
import {CssLikeObject} from '../types/common';

export interface CacheAddon {
    cache(css: CssLikeObject): string;
}

export function addon(nano: NanoRenderer);
