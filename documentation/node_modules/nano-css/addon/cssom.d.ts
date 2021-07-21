import {NanoRenderer} from '../types/nano';

export interface CSSOMRule extends CSSRule {
    index: number;
    style: CSSStyleDeclaration;
    styleMap: any;
}

export interface CSSOMAddon {
    /**
     * @param selector CSS rule selector string.
     * @param prelude Media query at-rule prelude string.
     */
    createRule(selector: string, prelude?: string): CSSOMRule;
}

export function addon(nano: NanoRenderer);
