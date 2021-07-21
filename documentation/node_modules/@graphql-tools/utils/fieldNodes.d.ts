import { FieldNode, FragmentDefinitionNode } from 'graphql';
export declare function renameFieldNode(fieldNode: FieldNode, name: string): FieldNode;
export declare function preAliasFieldNode(fieldNode: FieldNode, str: string): FieldNode;
export declare function wrapFieldNode(fieldNode: FieldNode, path: Array<string>): FieldNode;
export declare function hoistFieldNodes({ fieldNode, fieldNames, path, delimeter, fragments, }: {
    fieldNode: FieldNode;
    fieldNames?: Array<string>;
    path?: Array<string>;
    delimeter?: string;
    fragments: Record<string, FragmentDefinitionNode>;
}): Array<FieldNode>;
