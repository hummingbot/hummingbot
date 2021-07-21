import { GraphQLSchema } from 'graphql';
import { VisitorSelector, SchemaVisitorMap } from './Interfaces';
import { SchemaVisitor } from './SchemaVisitor';
export declare function visitSchema(schema: GraphQLSchema, visitorOrVisitorSelector: VisitorSelector | Array<SchemaVisitor | SchemaVisitorMap> | SchemaVisitor | SchemaVisitorMap): GraphQLSchema;
