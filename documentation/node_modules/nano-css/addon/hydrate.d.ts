import {NanoRenderer} from '../types/nano';

export interface HydrateAddon {
    hydrate(sh: HTMLStyleElement);
}

export function addon(nano: NanoRenderer);
