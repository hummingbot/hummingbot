import { Config } from './merge-typedefs';
import { InterfaceTypeDefinitionNode, InterfaceTypeExtensionNode } from 'graphql';
export declare function mergeInterface(node: InterfaceTypeDefinitionNode | InterfaceTypeExtensionNode, existingNode: InterfaceTypeDefinitionNode | InterfaceTypeExtensionNode, config: Config): InterfaceTypeDefinitionNode | InterfaceTypeExtensionNode;
