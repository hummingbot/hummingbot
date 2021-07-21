import { UnionTypeDefinitionNode, UnionTypeExtensionNode } from 'graphql';
import { Config } from './merge-typedefs';
export declare function mergeUnion(first: UnionTypeDefinitionNode | UnionTypeExtensionNode, second: UnionTypeDefinitionNode | UnionTypeExtensionNode, config?: Config): UnionTypeDefinitionNode | UnionTypeExtensionNode;
