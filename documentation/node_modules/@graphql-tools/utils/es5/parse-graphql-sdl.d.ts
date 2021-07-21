import { ParseOptions, DocumentNode, ASTNode, StringValueNode } from 'graphql';
export interface ExtendedParseOptions extends ParseOptions {
    /**
     * Set to `true` in order to convert all GraphQL comments (marked with # sign) to descriptions (""")
     * GraphQL has built-in support for transforming descriptions to comments (with `print`), but not while
     * parsing. Turning the flag on will support the other way as well (`parse`)
     */
    commentDescriptions?: boolean;
}
export declare function parseGraphQLSDL(location: string, rawSDL: string, options?: ExtendedParseOptions): {
    location: string;
    document: DocumentNode;
    rawSDL: string;
};
export declare function getLeadingCommentBlock(node: ASTNode): void | string;
export declare function transformCommentsToDescriptions(sourceSdl: string, options?: ExtendedParseOptions): DocumentNode | null;
declare type DiscriminateUnion<T, U> = T extends U ? T : never;
declare type DescribableASTNodes = DiscriminateUnion<ASTNode, {
    description?: StringValueNode;
}>;
export declare function isDescribable(node: ASTNode): node is DescribableASTNodes;
export {};
