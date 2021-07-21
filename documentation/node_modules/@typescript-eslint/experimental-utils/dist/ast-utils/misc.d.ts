import { TSESTree } from '../ts-estree';
declare const LINEBREAK_MATCHER: RegExp;
/**
 * Determines whether two adjacent tokens are on the same line
 */
declare function isTokenOnSameLine(left: TSESTree.Token | TSESTree.Comment, right: TSESTree.Token | TSESTree.Comment): boolean;
export { isTokenOnSameLine, LINEBREAK_MATCHER };
//# sourceMappingURL=misc.d.ts.map