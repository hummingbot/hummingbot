import { ValidationContext, SDLValidationContext } from '../ValidationContext';
import { ASTVisitor } from '../../language/visitor';

export function unknownArgMessage(
  argName: string,
  fieldName: string,
  typeName: string,
  suggestedArgs: ReadonlyArray<string>,
): string;

export function unknownDirectiveArgMessage(
  argName: string,
  directiveName: string,
  suggestedArgs: ReadonlyArray<string>,
): string;

/**
 * Known argument names
 *
 * A GraphQL field is only valid if all supplied arguments are defined by
 * that field.
 */
export function KnownArgumentNames(context: ValidationContext): ASTVisitor;

// @internal
export function KnownArgumentNamesOnDirectives(
  context: ValidationContext | SDLValidationContext,
): ASTVisitor;
