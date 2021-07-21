import { Config } from './merge-typedefs';
import { InputObjectTypeDefinitionNode } from 'graphql';
import { InputObjectTypeExtensionNode } from 'graphql/language/ast';
export declare function mergeInputType(node: InputObjectTypeDefinitionNode | InputObjectTypeExtensionNode, existingNode: InputObjectTypeDefinitionNode | InputObjectTypeExtensionNode, config?: Config): InputObjectTypeDefinitionNode | InputObjectTypeExtensionNode;
