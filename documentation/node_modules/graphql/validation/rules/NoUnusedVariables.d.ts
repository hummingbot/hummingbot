import Maybe from '../../tsutils/Maybe';
import { ASTVisitor } from '../../language/visitor';
import { ValidationContext } from '../ValidationContext';

export function unusedVariableMessage(
  varName: string,
  opName: Maybe<string>,
): string;

/**
 * No unused variables
 *
 * A GraphQL operation is only valid if all variables defined by an operation
 * are used, either directly or within a spread fragment.
 */
export function NoUnusedVariables(context: ValidationContext): ASTVisitor;
