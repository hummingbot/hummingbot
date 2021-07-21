import Maybe from '../tsutils/Maybe';
import { GraphQLFieldConfigArgumentMap, GraphQLArgument } from './definition';
import { DirectiveDefinitionNode } from '../language/ast';
import { DirectiveLocationEnum } from '../language/directiveLocation';

/**
 * Test if the given value is a GraphQL directive.
 */
export function isDirective(directive: any): directive is GraphQLDirective;
export function assertDirective(directive: any): GraphQLDirective;
/**
 * Directives are used by the GraphQL runtime as a way of modifying execution
 * behavior. Type system creators will usually not create these directly.
 */
export class GraphQLDirective {
  name: string;
  description: Maybe<string>;
  locations: DirectiveLocationEnum[];
  isRepeatable: boolean;
  args: GraphQLArgument[];
  extensions?: Maybe<Readonly<Record<string, any>>>;
  astNode: Maybe<DirectiveDefinitionNode>;

  constructor(config: GraphQLDirectiveConfig);

  toString(): string;

  toConfig(): GraphQLDirectiveConfig & {
    args: GraphQLFieldConfigArgumentMap;
    extensions?: Maybe<Readonly<Record<string, any>>>;
    isRepeatable: boolean;
  };
}

export interface GraphQLDirectiveConfig {
  name: string;
  description?: Maybe<string>;
  locations: DirectiveLocationEnum[];
  args?: Maybe<GraphQLFieldConfigArgumentMap>;
  isRepeatable?: Maybe<boolean>;
  extensions?: Maybe<Readonly<Record<string, any>>>;
  astNode?: Maybe<DirectiveDefinitionNode>;
}

/**
 * Used to conditionally include fields or fragments.
 */
export const GraphQLIncludeDirective: GraphQLDirective;

/**
 * Used to conditionally skip (exclude) fields or fragments.
 */
export const GraphQLSkipDirective: GraphQLDirective;

/**
 * Constant string used for default reason for a deprecation.
 */
export const DEFAULT_DEPRECATION_REASON: 'No longer supported';

/**
 * Used to declare element of a GraphQL schema as deprecated.
 */
export const GraphQLDeprecatedDirective: GraphQLDirective;

/**
 * The full list of specified directives.
 */
export const specifiedDirectives: ReadonlyArray<GraphQLDirective>;

export function isSpecifiedDirective(directive: any): boolean;
