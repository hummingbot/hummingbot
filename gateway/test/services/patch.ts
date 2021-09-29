let patchedObjects: Set<any> = new Set();

// override an existing property value, but make the old one recoverable.
export const patch = (target: any, propertyName: string, mock: any): void => {
  // clean up a target if it has already been patched, this avoids issues in unpatch
  if (patchedObjects.has(target)) patchedObjects.delete(target);

  // only store the previous property if it has not been mocked yet, this way we preserve
  // the original non mocked value
  if (!('__original__' + propertyName in target))
    target['__original__' + propertyName] = target[propertyName];

  target[propertyName] = mock;
  patchedObjects.add(target);
};

// recover all old property values from before the patch.
export const unpatch = (): void => {
  patchedObjects.forEach((target: any) => {
    const keys = Object.keys(target);
    keys.forEach((key: string) => {
      if (key.startsWith('__original__')) {
        const propertyName = key.slice(12);
        target[propertyName] = target[key];
        delete target[key];
      }
    });
  });
  patchedObjects = new Set();
};
