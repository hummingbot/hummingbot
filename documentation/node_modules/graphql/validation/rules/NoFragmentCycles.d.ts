import { ASTVisitor } from '../../language/visitor';
import { ValidationContext } from '../ValidationContext';

export function cycleErrorMessage(
  fragName: string,
  spreadNames: ReadonlyArray<string>,
): string;

export function NoFragmentCycles(context: ValidationContext): ASTVisitor;
