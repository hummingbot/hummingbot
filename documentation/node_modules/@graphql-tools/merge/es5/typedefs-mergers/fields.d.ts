import { Config } from './merge-typedefs';
import { FieldDefinitionNode, InputValueDefinitionNode, NameNode } from 'graphql';
export declare function mergeFields<T extends FieldDefinitionNode | InputValueDefinitionNode>(type: {
    name: NameNode;
}, f1: ReadonlyArray<T>, f2: ReadonlyArray<T>, config: Config): T[];
