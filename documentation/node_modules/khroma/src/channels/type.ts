
/* IMPORT */

import {TYPE} from '../types';

/* TYPE */

class Type {

  type: TYPE = TYPE.ALL;

  get (): TYPE {

    return this.type;

  }

  set ( type: TYPE ): void {

    if ( this.type && this.type !== type ) throw new Error ( 'Cannot change both RGB and HSL channels at the same time' );

    this.type = type;

  }

  reset (): void {

    this.type = TYPE.ALL;

  }

  is ( type: TYPE ): boolean {

    return this.type === type;

  }

}

/* EXPORT */

export default Type;
