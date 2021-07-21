import { ASTNode } from 'graphql';
export declare const asArray: <T>(fns: T | T[]) => T[];
export declare function isEqual<T>(a: T, b: T): boolean;
export declare function isNotEqual<T>(a: T, b: T): boolean;
export declare function isDocumentString(str: string): boolean;
export declare function isValidPath(str: string): boolean;
export declare function compareStrings<A, B>(a: A, b: B): 1 | 0 | -1;
export declare function nodeToString(a: ASTNode): string;
export declare function compareNodes(a: ASTNode, b: ASTNode, customFn?: (a: any, b: any) => number): number;
