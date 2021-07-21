import { NamedTypeNode } from 'graphql/language/ast';
import { Config } from '.';
export declare function mergeNamedTypeArray(first: ReadonlyArray<NamedTypeNode>, second: ReadonlyArray<NamedTypeNode>, config: Config): NamedTypeNode[];
