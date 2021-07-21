import { GraphQLObjectType, SelectionSetNode, FieldNode } from 'graphql';
import { GraphQLExecutionContext } from './Interfaces';
/**
 * Given a selectionSet, adds all of the fields in that selection to
 * the passed in map of fields, and returns it at the end.
 *
 * CollectFields requires the "runtime type" of an object. For a field which
 * returns an Interface or Union type, the "runtime type" will be the actual
 * Object type returned by that field.
 *
 * @internal
 */
export declare function collectFields(exeContext: GraphQLExecutionContext, runtimeType: GraphQLObjectType, selectionSet: SelectionSetNode, fields: Record<string, Array<FieldNode>>, visitedFragmentNames: Record<string, boolean>): Record<string, Array<FieldNode>>;
