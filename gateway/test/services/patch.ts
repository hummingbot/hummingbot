let patchedObjects: Set<any> = new Set();

export const classHasGetter = (obj: any, prop: string): boolean => {
  const description = Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(obj),
    prop
  );
  if (description) {
    return !!description.get;
  }
  return false;
};

// override an existing property value, but make the old one recoverable.
export const patch = (target: any, propertyName: string, mock: any): void => {
  // clean up a target if it has already been patched, this avoids issues in unpatch
  if (patchedObjects.has(target)) patchedObjects.delete(target);

  // only store the previous property if it has not been mocked yet, this way we preserve
  // the original non mocked value
  if (!('__original__' + propertyName in target)) {
    if (Object.getOwnPropertyDescriptor(target, propertyName)) {
      // general case
      target['__original__' + propertyName] = target[propertyName];
    } else {
      // special case for getters and setters
      target['__original__' + propertyName] = Object.getOwnPropertyDescriptor(
        Object.getPrototypeOf(target),
        propertyName
      );
    }
  }

  if (classHasGetter(target, propertyName)) {
    // special case for getter without setter
    const targetPrototype = Object.getPrototypeOf(target);

    Object.defineProperty(targetPrototype, propertyName, {
      get: mock,
      // this is a dummy setter, there needs to be a setter in order to change the getter
      // the idea is that the mock overrides the getter and ignores the setter
      set: (_value: any) => {
        return;
      },
    });

    Object.setPrototypeOf(target, targetPrototype);
  } else {
    // general case
    target[propertyName] = mock;
  }

  patchedObjects.add(target);
};

// recover all old property values from before the patch.
export const unpatch = (): void => {
  patchedObjects.forEach((target: any) => {
    const keys = Object.keys(target);
    keys.forEach((key: string) => {
      if (key.startsWith('__original__')) {
        const propertyName = key.slice(12);

        if (Object.getOwnPropertyDescriptor(target, propertyName)) {
          // the property exists directly on the object
          target[propertyName] = target[key];
        } else {
          // the property is at a lower level in the object, it is likely a getter or setter
          const targetPrototype = Object.getPrototypeOf(target);

          Object.defineProperty(targetPrototype, propertyName, target[key]);
          Object.setPrototypeOf(target, targetPrototype);
        }

        delete target[key];
      }
    });
  });
  patchedObjects = new Set();
};
