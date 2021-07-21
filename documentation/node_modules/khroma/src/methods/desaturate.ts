
/* IMPORT */

import Channels from '../channels';
import adjustChannel from './adjust_channel';

/* DESATURATE */

function desaturate ( color: string | Channels, amount: number ): string {

  return adjustChannel ( color, 's', -amount );

}

/* EXPORT */

export default desaturate;
