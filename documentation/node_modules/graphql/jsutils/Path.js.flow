// @flow strict

export type Path = {|
  +prev: Path | void,
  +key: string | number,
|};

/**
 * Given a Path and a key, return a new Path containing the new key.
 */
export function addPath(prev: $ReadOnly<Path> | void, key: string | number) {
  return { prev, key };
}

/**
 * Given a Path, return an Array of the path keys.
 */
export function pathToArray(path: ?$ReadOnly<Path>): Array<string | number> {
  const flattened = [];
  let curr = path;
  while (curr) {
    flattened.push(curr.key);
    curr = curr.prev;
  }
  return flattened.reverse();
}
