import { ParserServices, TSESTree } from '../ts-estree';
import { Scope } from './Scope';
interface SourceCode {
    text: string;
    ast: SourceCode.Program;
    lines: string[];
    hasBOM: boolean;
    parserServices: ParserServices;
    scopeManager: Scope.ScopeManager;
    visitorKeys: SourceCode.VisitorKeys;
    tokensAndComments: (TSESTree.Comment | TSESTree.Token)[];
    getText(node?: TSESTree.Node, beforeCount?: number, afterCount?: number): string;
    getLines(): string[];
    getAllComments(): TSESTree.Comment[];
    getComments(node: TSESTree.Node): {
        leading: TSESTree.Comment[];
        trailing: TSESTree.Comment[];
    };
    getJSDocComment(node: TSESTree.Node): TSESTree.Node | TSESTree.Token | null;
    getNodeByRangeIndex(index: number): TSESTree.Node | null;
    isSpaceBetween(first: TSESTree.Token | TSESTree.Comment | TSESTree.Node, second: TSESTree.Token | TSESTree.Comment | TSESTree.Node): boolean;
    /**
     * @deprecated in favor of isSpaceBetween()
     */
    isSpaceBetweenTokens(first: TSESTree.Token, second: TSESTree.Token): boolean;
    getLocFromIndex(index: number): TSESTree.LineAndColumnData;
    getIndexFromLoc(location: TSESTree.LineAndColumnData): number;
    getTokenByRangeStart<T extends {
        includeComments?: boolean;
    }>(offset: number, options?: T): SourceCode.ReturnTypeFromOptions<T> | null;
    getFirstToken<T extends SourceCode.CursorWithSkipOptions>(node: TSESTree.Node, options?: T): SourceCode.ReturnTypeFromOptions<T> | null;
    getFirstTokens<T extends SourceCode.CursorWithCountOptions>(node: TSESTree.Node, options?: T): SourceCode.ReturnTypeFromOptions<T>[];
    getLastToken<T extends SourceCode.CursorWithSkipOptions>(node: TSESTree.Node, options?: T): SourceCode.ReturnTypeFromOptions<T> | null;
    getLastTokens<T extends SourceCode.CursorWithCountOptions>(node: TSESTree.Node, options?: T): SourceCode.ReturnTypeFromOptions<T>[];
    getTokenBefore<T extends SourceCode.CursorWithSkipOptions>(node: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T> | null;
    getTokensBefore<T extends SourceCode.CursorWithCountOptions>(node: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T>[];
    getTokenAfter<T extends SourceCode.CursorWithSkipOptions>(node: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T> | null;
    getTokensAfter<T extends SourceCode.CursorWithCountOptions>(node: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T>[];
    getFirstTokenBetween<T extends SourceCode.CursorWithSkipOptions>(left: TSESTree.Node | TSESTree.Token | TSESTree.Comment, right: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T> | null;
    getFirstTokensBetween<T extends SourceCode.CursorWithCountOptions>(left: TSESTree.Node | TSESTree.Token | TSESTree.Comment, right: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T>[];
    getLastTokenBetween<T extends SourceCode.CursorWithSkipOptions>(left: TSESTree.Node | TSESTree.Token | TSESTree.Comment, right: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T> | null;
    getLastTokensBetween<T extends SourceCode.CursorWithCountOptions>(left: TSESTree.Node | TSESTree.Token | TSESTree.Comment, right: TSESTree.Node | TSESTree.Token | TSESTree.Comment, options?: T): SourceCode.ReturnTypeFromOptions<T>[];
    getTokensBetween<T extends SourceCode.CursorWithCountOptions>(left: TSESTree.Node | TSESTree.Token | TSESTree.Comment, right: TSESTree.Node | TSESTree.Token | TSESTree.Comment, padding?: T): SourceCode.ReturnTypeFromOptions<T>[];
    getTokens(node: TSESTree.Node, beforeCount?: number, afterCount?: number): TSESTree.Token[];
    getTokens<T extends SourceCode.CursorWithCountOptions>(node: TSESTree.Node, options: T): SourceCode.ReturnTypeFromOptions<T>[];
    commentsExistBetween(left: TSESTree.Node | TSESTree.Token, right: TSESTree.Node | TSESTree.Token): boolean;
    getCommentsBefore(nodeOrToken: TSESTree.Node | TSESTree.Token): TSESTree.Comment[];
    getCommentsAfter(nodeOrToken: TSESTree.Node | TSESTree.Token): TSESTree.Comment[];
    getCommentsInside(node: TSESTree.Node): TSESTree.Comment[];
}
declare namespace SourceCode {
    interface Program extends TSESTree.Program {
        comments: TSESTree.Comment[];
        tokens: TSESTree.Token[];
    }
    interface Config {
        text: string;
        ast: Program;
        parserServices?: ParserServices;
        scopeManager?: Scope.ScopeManager;
        visitorKeys?: VisitorKeys;
    }
    interface VisitorKeys {
        [nodeType: string]: string[];
    }
    type FilterPredicate = (tokenOrComment: TSESTree.Token | TSESTree.Comment) => boolean;
    type ReturnTypeFromOptions<T> = T extends {
        includeComments: true;
    } ? TSESTree.Token | TSESTree.Comment : TSESTree.Token;
    type CursorWithSkipOptions = number | FilterPredicate | {
        includeComments?: boolean;
        filter?: FilterPredicate;
        skip?: number;
    };
    type CursorWithCountOptions = number | FilterPredicate | {
        includeComments?: boolean;
        filter?: FilterPredicate;
        count?: number;
    };
}
declare const SourceCode: {
    new (text: string, ast: SourceCode.Program): SourceCode;
    new (config: SourceCode.Config): SourceCode;
    splitLines(text: string): string[];
};
export { SourceCode };
//# sourceMappingURL=SourceCode.d.ts.map