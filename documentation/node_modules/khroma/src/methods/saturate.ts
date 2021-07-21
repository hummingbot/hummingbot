
/* IMPORT */

import Channels from '../channels';
import adjustChannel from './adjust_channel';

/* SATURATE */

function saturate ( color: string | Channels, amount: number ): string {

  return adjustChannel ( color, 's', amount );

}

/* EXPORT */

export default saturate;
