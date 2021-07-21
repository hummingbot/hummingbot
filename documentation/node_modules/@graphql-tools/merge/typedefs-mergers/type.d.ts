import { Config } from './merge-typedefs';
import { ObjectTypeDefinitionNode, ObjectTypeExtensionNode } from 'graphql';
export declare function mergeType(node: ObjectTypeDefinitionNode | ObjectTypeExtensionNode, existingNode: ObjectTypeDefinitionNode | ObjectTypeExtensionNode, config?: Config): ObjectTypeDefinitionNode | ObjectTypeExtensionNode;
