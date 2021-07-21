
/* IMPORT */

import Channels from '../channels';
import adjustChannel from './adjust_channel';

/* LIGHTEN */

function lighten ( color: string | Channels, amount: number ): string {

  return adjustChannel ( color, 'l', amount );

}

/* EXPORT */

export default lighten;
