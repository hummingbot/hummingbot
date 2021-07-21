import { GraphQLDirective, GraphQLNamedType } from 'graphql';
import { TypeMap } from './Interfaces';
export declare function rewireTypes(originalTypeMap: Record<string, GraphQLNamedType | null>, directives: ReadonlyArray<GraphQLDirective>, options?: {
    skipPruning: boolean;
}): {
    typeMap: TypeMap;
    directives: Array<GraphQLDirective>;
};
