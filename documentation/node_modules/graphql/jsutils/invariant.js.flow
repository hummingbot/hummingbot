// @flow strict

export default function invariant(condition: mixed, message?: string): void {
  const booleanCondition = Boolean(condition);
  if (!booleanCondition) {
    throw new Error(message || 'Unexpected invariant triggered');
  }
}
