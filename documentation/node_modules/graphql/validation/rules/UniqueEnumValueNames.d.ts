import { ASTVisitor } from '../../language/visitor';
import { SDLValidationContext } from '../ValidationContext';

export function duplicateEnumValueNameMessage(
  typeName: string,
  valueName: string,
): string;

export function existedEnumValueNameMessage(
  typeName: string,
  valueName: string,
): string;

/**
 * Unique enum value names
 *
 * A GraphQL enum type is only valid if all its values are uniquely named.
 */
export function UniqueEnumValueNames(context: SDLValidationContext): ASTVisitor;
