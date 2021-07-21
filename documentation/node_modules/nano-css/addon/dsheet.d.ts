import {NanoRenderer} from '../types/nano';
import {CssLikeObject} from '../types/common';

export interface DsheetAddon {
    dsheet(map: object, block?: string): object;
}

export function addon(nano: NanoRenderer);
