// @flow strict

export default function devAssert(condition: mixed, message: string): void {
  const booleanCondition = Boolean(condition);
  if (!booleanCondition) {
    throw new Error(message);
  }
}
