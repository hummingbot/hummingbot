import {NanoRenderer} from '../types/nano';

export interface Units {
    /**
     * Adds `px` postfix.
     */
    px: (val: number) => string;

    /**
     * Adds `cm` postfix.
     */
    cm: (val: number) => string;

    /**
     * Adds `pt` postfix.
     */
    pt: (val: number) => string;

    /**
     * Adds `pc` postfix.
     */
    pc: (val: number) => string;

    /**
     * Adds `em` postfix.
     */
    em: (val: number) => string;

    /**
     * Adds `ex` postfix.
     */
    ex: (val: number) => string;

    /**
     * Adds `ch` postfix.
     */
    ch: (val: number) => string;

    /**
     * Adds `rem` postfix.
     */
    rem: (val: number) => string;

    /**
     * Adds `vw` postfix.
     */
    vw: (val: number) => string;

    /**
     * Adds `vh` postfix.
     */
    vh: (val: number) => string;

    /**
     * Adds `deg` postfix.
     */
    deg: (val: number) => string;

    /**
     * Adds `vmin` postfix.
     */
    vmin: (val: number) => string;

    /**
     * Adds `vmax` postfix.
     */
    vmax: (val: number) => string;

    /**
     * Adds `in` postfix.
     */
    inch: (val: number) => string;

    /**
     * Adds `in` postfix.
     */
    in: (val: number) => string;

    /**
     * Adds `%` postfix.
     */
    pct: (val: number) => string;
}

export interface UnitsAddon extends Units {
    units: Units;
}

export function addon(nano: NanoRenderer);
