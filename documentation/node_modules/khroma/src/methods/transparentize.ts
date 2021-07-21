
/* IMPORT */

import Channels from '../channels';
import adjustChannel from './adjust_channel';

/* TRANSPARENTIZE */

function transparentize ( color: string | Channels, amount: number ): string {

  return adjustChannel ( color, 'a', -amount );

}

/* EXPORT */

export default transparentize;
