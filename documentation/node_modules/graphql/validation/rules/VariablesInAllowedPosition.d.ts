import { ASTVisitor } from '../../language/visitor';
import { ValidationContext } from '../ValidationContext';

export function badVarPosMessage(
  varName: string,
  varType: string,
  expectedType: string,
): string;

/**
 * Variables passed to field arguments conform to type
 */
export function VariablesInAllowedPosition(
  context: ValidationContext,
): ASTVisitor;
