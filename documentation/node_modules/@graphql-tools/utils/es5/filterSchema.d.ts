import { GraphQLSchema } from 'graphql';
import { FieldFilter, RootFieldFilter, TypeFilter } from './Interfaces';
export declare function filterSchema({ schema, rootFieldFilter, typeFilter, fieldFilter, objectFieldFilter, interfaceFieldFilter, }: {
    schema: GraphQLSchema;
    rootFieldFilter?: RootFieldFilter;
    typeFilter?: TypeFilter;
    fieldFilter?: FieldFilter;
    objectFieldFilter?: FieldFilter;
    interfaceFieldFilter?: FieldFilter;
}): GraphQLSchema;
