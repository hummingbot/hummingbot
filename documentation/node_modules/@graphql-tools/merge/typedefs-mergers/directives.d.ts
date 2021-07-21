import { DirectiveNode } from 'graphql/language/ast';
import { DirectiveDefinitionNode } from 'graphql';
import { Config } from './merge-typedefs';
export declare function mergeDirectives(d1?: ReadonlyArray<DirectiveNode>, d2?: ReadonlyArray<DirectiveNode>, config?: Config): DirectiveNode[];
export declare function mergeDirective(node: DirectiveDefinitionNode, existingNode?: DirectiveDefinitionNode): DirectiveDefinitionNode;
