
/* IMPORT */

import Channels from '../channels';
import change from './change';

/* GRAYSCALE */

function grayscale ( color: string | Channels ): string {

  return change ( color, { s: 0 } );

}

/* EXPORT */

export default grayscale;
