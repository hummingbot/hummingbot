import { ScalarTypeDefinitionNode, ScalarTypeExtensionNode } from 'graphql';
import { Config } from './merge-typedefs';
export declare function mergeScalar(node: ScalarTypeDefinitionNode | ScalarTypeExtensionNode, existingNode: ScalarTypeDefinitionNode | ScalarTypeExtensionNode, config?: Config): ScalarTypeDefinitionNode | ScalarTypeExtensionNode;
