import {NanoRenderer} from '../types/nano';
import {CssLikeObject} from '../types/common';

export interface GoogleFontAddon {
    googleFont(font: string, weights: number | string | (number | string)[], subsets: string | string[]);
}

export function addon(nano: NanoRenderer);
