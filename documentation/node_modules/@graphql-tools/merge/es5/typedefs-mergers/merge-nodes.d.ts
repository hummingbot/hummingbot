import { Config } from './merge-typedefs';
import { DefinitionNode } from 'graphql';
export declare type MergedResultMap = {
    [name: string]: DefinitionNode;
};
export declare function mergeGraphQLNodes(nodes: ReadonlyArray<DefinitionNode>, config?: Config): MergedResultMap;
