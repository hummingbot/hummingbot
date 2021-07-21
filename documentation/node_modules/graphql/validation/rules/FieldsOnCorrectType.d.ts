import { ASTVisitor } from '../../language/visitor';
import { ValidationContext } from '../ValidationContext';

export function undefinedFieldMessage(
  fieldName: string,
  type: string,
  suggestedTypeNames: ReadonlyArray<string>,
  suggestedFieldNames: ReadonlyArray<string>,
): string;

/**
 * Fields on correct type
 *
 * A GraphQL document is only valid if all fields selected are defined by the
 * parent type, or are an allowed meta field such as __typename.
 */
export function FieldsOnCorrectType(context: ValidationContext): ASTVisitor;
