
/* IMPORT */

import Channels from '../channels';
import luminance from './luminance';

/* IS LIGHT */

function isLight ( color: string | Channels ): boolean {

  return luminance ( color ) >= .5;

}

/* EXPORT */

export default isLight;
