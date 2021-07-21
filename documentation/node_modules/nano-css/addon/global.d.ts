import {NanoRenderer} from '../types/nano';
import {CssLikeObject} from '../types/common';

export interface GlobalAddon {
    global(css: CssLikeObject);
}

export function addon(nano: NanoRenderer);
