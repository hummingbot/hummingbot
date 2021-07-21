import { GraphQLArgument, GraphQLEnumType, GraphQLEnumValue, GraphQLField, GraphQLInputField, GraphQLInputObjectType, GraphQLInterfaceType, GraphQLObjectType, GraphQLScalarType, GraphQLSchema, GraphQLUnionType } from 'graphql';
export declare abstract class SchemaVisitor {
    schema: GraphQLSchema;
    static implementsVisitorMethod(methodName: string): boolean;
    visitSchema(_schema: GraphQLSchema): void;
    visitScalar(_scalar: GraphQLScalarType): GraphQLScalarType | void | null;
    visitObject(_object: GraphQLObjectType): GraphQLObjectType | void | null;
    visitFieldDefinition(_field: GraphQLField<any, any>, _details: {
        objectType: GraphQLObjectType | GraphQLInterfaceType;
    }): GraphQLField<any, any> | void | null;
    visitArgumentDefinition(_argument: GraphQLArgument, _details: {
        field: GraphQLField<any, any>;
        objectType: GraphQLObjectType | GraphQLInterfaceType;
    }): GraphQLArgument | void | null;
    visitInterface(_iface: GraphQLInterfaceType): GraphQLInterfaceType | void | null;
    visitUnion(_union: GraphQLUnionType): GraphQLUnionType | void | null;
    visitEnum(_type: GraphQLEnumType): GraphQLEnumType | void | null;
    visitEnumValue(_value: GraphQLEnumValue, _details: {
        enumType: GraphQLEnumType;
    }): GraphQLEnumValue | void | null;
    visitInputObject(_object: GraphQLInputObjectType): GraphQLInputObjectType | void | null;
    visitInputFieldDefinition(_field: GraphQLInputField, _details: {
        objectType: GraphQLInputObjectType;
    }): GraphQLInputField | void | null;
}
