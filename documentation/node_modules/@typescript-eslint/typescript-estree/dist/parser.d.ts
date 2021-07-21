import { TSESTreeOptions, ParserServices } from './parser-options';
import { TSESTree } from './ts-estree';
declare type AST<T extends TSESTreeOptions> = TSESTree.Program & (T['tokens'] extends true ? {
    tokens: TSESTree.Token[];
} : {}) & (T['comment'] extends true ? {
    comments: TSESTree.Comment[];
} : {});
interface ParseAndGenerateServicesResult<T extends TSESTreeOptions> {
    ast: AST<T>;
    services: ParserServices;
}
declare const version: string;
declare function parse<T extends TSESTreeOptions = TSESTreeOptions>(code: string, options?: T): AST<T>;
declare function parseAndGenerateServices<T extends TSESTreeOptions = TSESTreeOptions>(code: string, options: T): ParseAndGenerateServicesResult<T>;
export { AST, parse, parseAndGenerateServices, ParseAndGenerateServicesResult, version, };
export { ParserServices, TSESTreeOptions } from './parser-options';
export { simpleTraverse } from './simple-traverse';
export { visitorKeys } from './visitor-keys';
export * from './ts-estree';
export { clearCaches } from './create-program/createWatchProgram';
//# sourceMappingURL=parser.d.ts.map