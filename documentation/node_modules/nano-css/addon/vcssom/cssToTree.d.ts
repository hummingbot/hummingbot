import {CssLikeObject} from '../../types/common';

export interface Css {
    [key: string]: CssLikeObject[keyof CssLikeObject] | Css;
}

export interface Tree {
    [atRulePrelude: string]: {
        [selector: string]: {
            [property: string]: CssLikeObject;
        };
    };
}

export function cssToTree(tree: {}, css: Css, selector: string, prelude: string): Tree;
