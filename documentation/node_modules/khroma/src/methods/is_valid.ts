
/* IMPORT */

import Color from '../color';

/* IS VALID */

function isValid ( color: string ): boolean {

  try {

    Color.parse ( color );

    return true;

  } catch {

    return false;

  }

}

/* EXPORT */

export default isValid;
