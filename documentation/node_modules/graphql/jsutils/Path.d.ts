export type Path = {
  prev: Path | undefined;
  key: string | number;
};

/**
 * Given a Path and a key, return a new Path containing the new key.
 */
export function addPath(prev: Path | undefined, key: string | number): Path;

/**
 * Given a Path, return an Array of the path keys.
 */
export function pathToArray(path: Path): Array<string | number>;
