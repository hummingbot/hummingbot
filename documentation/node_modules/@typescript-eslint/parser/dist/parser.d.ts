import { TSESLint } from '@typescript-eslint/experimental-utils';
import { AST_NODE_TYPES, ParserServices, TSESTree, visitorKeys } from '@typescript-eslint/typescript-estree';
import { analyzeScope } from './analyze-scope';
declare type ParserOptions = TSESLint.ParserOptions;
interface ParseForESLintResult {
    ast: TSESTree.Program & {
        range?: [number, number];
        tokens?: TSESTree.Token[];
        comments?: TSESTree.Comment[];
    };
    services: ParserServices;
    visitorKeys: typeof visitorKeys;
    scopeManager: ReturnType<typeof analyzeScope>;
}
export declare const version: any;
export declare const Syntax: Readonly<typeof AST_NODE_TYPES>;
export declare function parse(code: string, options?: ParserOptions): ParseForESLintResult['ast'];
export declare function parseForESLint(code: string, options?: ParserOptions | null): ParseForESLintResult;
export { ParserServices, ParserOptions };
export { clearCaches } from '@typescript-eslint/typescript-estree';
//# sourceMappingURL=parser.d.ts.map