import { ASTVisitor } from '../../language/visitor';
import { SDLValidationContext } from '../ValidationContext';

export function extendingUnknownTypeMessage(
  typeName: string,
  suggestedTypes: ReadonlyArray<string>,
): string;

export function extendingDifferentTypeKindMessage(
  typeName: string,
  kind: string,
): string;

/**
 * Possible type extension
 *
 * A type extension is only valid if the type is defined and has the same kind.
 */
export function PossibleTypeExtensions(
  context: SDLValidationContext,
): ASTVisitor;
