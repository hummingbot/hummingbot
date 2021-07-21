import { ASTVisitor } from '../../language/visitor';
import { SDLValidationContext } from '../ValidationContext';

export function duplicateFieldDefinitionNameMessage(
  typeName: string,
  fieldName: string,
): string;

export function existedFieldDefinitionNameMessage(
  typeName: string,
  fieldName: string,
): string;

/**
 * Unique field definition names
 *
 * A GraphQL complex type is only valid if all its fields are uniquely named.
 */
export function UniqueFieldDefinitionNames(
  context: SDLValidationContext,
): ASTVisitor;
