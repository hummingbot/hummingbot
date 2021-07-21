import { SelectionSetNode, GraphQLObjectType } from 'graphql';
export declare function parseSelectionSet(selectionSet: string): SelectionSetNode;
export declare function typesContainSelectionSet(types: Array<GraphQLObjectType>, selectionSet: SelectionSetNode): boolean;
export declare function typeContainsSelectionSet(type: GraphQLObjectType, selectionSet: SelectionSetNode): boolean;
