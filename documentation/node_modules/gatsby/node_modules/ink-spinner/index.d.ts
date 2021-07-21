// Type definitions ported from DefinitelyTyped
// Ported by: M4rk9696 <https://github.com/M4rk9696>
// Original Definitions by: Łukasz Ostrowski <https://github.com/lukostry>

import { Chalk } from 'chalk';
import type {SpinnerName} from 'cli-spinners';
import type { Component } from 'react';

type StringifyPartial<T> = {
    [P in keyof T]?: string;
};

type BooleansPartial<T> = {
    [P in keyof T]?: boolean;
};

type TupleOfNumbersPartial<T> = {
    [P in keyof T]?: [number, number, number];
};
// Omit taken from https://www.typescriptlang.org/docs/handbook/release-notes/typescript-2-8.html
type Omit<T, K> = Pick<T, Exclude<keyof T, K>>;

type ChalkColorModels = Pick<Chalk, 'rgb' | 'hsl' | 'hsv' | 'hwb' | 'bgRgb' | 'bgHsl' | 'bgHsv' | 'bgHwb'>;
type ChalkKeywordsAndHexes = Pick<Chalk, 'keyword' | 'hex' | 'bgKeyword' | 'bgHex'>;
type ChalkCommons = Omit<Chalk, keyof ChalkColorModels | keyof ChalkKeywordsAndHexes | 'constructor' | 'level' | 'enabled'>;

interface SpinnerProps {
    type?: SpinnerName;
}

type ChalkProps = BooleansPartial<ChalkCommons>
    & StringifyPartial<ChalkKeywordsAndHexes>
    & TupleOfNumbersPartial<ChalkColorModels>;

declare class Spinner extends Component<SpinnerProps & ChalkProps> { }

export = Spinner;
