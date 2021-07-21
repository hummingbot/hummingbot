import { StringValueNode, TypeDefinitionNode, ASTNode } from 'graphql';
export declare function resetComments(): void;
export declare function collectComment(node: TypeDefinitionNode): void;
export declare function pushComment(node: {
    readonly description?: StringValueNode;
}, entity: string, field?: string, argument?: string): void;
export declare function printComment(comment: string): string;
/**
 * Converts an AST into a string, using one set of reasonable
 * formatting rules.
 */
export declare function printWithComments(ast: ASTNode): any;
