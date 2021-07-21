import { Kind } from '../language/kinds';
import { visit, visitWithTypeInfo } from '../language/visitor';
import { ValuesOfCorrectType } from '../validation/rules/ValuesOfCorrectType';
import { ValidationContext } from '../validation/ValidationContext';
import { GraphQLSchema } from '../type/schema';
import { TypeInfo } from './TypeInfo';
/**
 * Utility which determines if a value literal node is valid for an input type.
 *
 * Deprecated. Rely on validation for documents containing literal values.
 *
 * This function will be removed in v15
 */

export function isValidLiteralValue(type, valueNode) {
  var emptySchema = new GraphQLSchema({});
  var emptyDoc = {
    kind: Kind.DOCUMENT,
    definitions: []
  };
  var typeInfo = new TypeInfo(emptySchema, undefined, type);
  var context = new ValidationContext(emptySchema, emptyDoc, typeInfo);
  var visitor = ValuesOfCorrectType(context);
  visit(valueNode, visitWithTypeInfo(typeInfo, visitor));
  return context.getErrors();
}
