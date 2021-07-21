import { GraphQLInputType, ArgumentNode, VariableDefinitionNode } from 'graphql';
export declare function updateArgument(argName: string, argType: GraphQLInputType, argumentNodes: Record<string, ArgumentNode>, variableDefinitionsMap: Record<string, VariableDefinitionNode>, variableValues: Record<string, any>, newArg: any): void;
