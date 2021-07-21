
/* IMPORT */

import Channels from '../channels';
import adjustChannel from './adjust_channel';

/* OPACIFY */

function opacify ( color: string | Channels, amount: number ): string {

  return adjustChannel ( color, 'a', amount );

}

/* EXPORT */

export default opacify;
