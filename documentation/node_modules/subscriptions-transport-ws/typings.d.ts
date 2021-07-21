interface Array<T> {
  indexOfField : (propertyName: string, value: any) => number;
}

declare module 'lodash.assign' {
  import {assign} from 'lodash';
  export = assign;
}

declare module 'lodash.isobject' {
  import {isObject} from 'lodash';
  export = isObject;
}

declare module 'lodash.isstring' {
  import {isString} from 'lodash';
  export = isString;
}

declare module 'backo2';
