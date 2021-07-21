import { GraphQLDirective, GraphQLSchema } from 'graphql';
import { VisitableSchemaType } from './Interfaces';
import { SchemaVisitor } from './SchemaVisitor';
export declare class SchemaDirectiveVisitor<TArgs = any, TContext = any> extends SchemaVisitor {
    name: string;
    args: TArgs;
    visitedType: VisitableSchemaType;
    context: TContext;
    static getDirectiveDeclaration(directiveName: string, schema: GraphQLSchema): GraphQLDirective | null | undefined;
    static visitSchemaDirectives(schema: GraphQLSchema, directiveVisitors: Record<string, SchemaDirectiveVisitorClass>, context?: Record<string, any>): Record<string, Array<SchemaDirectiveVisitor>>;
    protected static getDeclaredDirectives(schema: GraphQLSchema, directiveVisitors: Record<string, SchemaDirectiveVisitorClass>): Record<string, GraphQLDirective>;
    protected constructor(config: {
        name: string;
        args: TArgs;
        visitedType: VisitableSchemaType;
        schema: GraphQLSchema;
        context: TContext;
    });
}
export declare type SchemaDirectiveVisitorClass = typeof SchemaDirectiveVisitor;
