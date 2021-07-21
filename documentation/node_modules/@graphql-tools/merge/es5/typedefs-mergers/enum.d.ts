import { EnumTypeDefinitionNode, EnumTypeExtensionNode } from 'graphql';
import { Config } from './merge-typedefs';
export declare function mergeEnum(e1: EnumTypeDefinitionNode | EnumTypeExtensionNode, e2: EnumTypeDefinitionNode | EnumTypeExtensionNode, config?: Config): EnumTypeDefinitionNode | EnumTypeExtensionNode;
