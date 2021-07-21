
/* IMPORT */

import Channels from '../channels';
import channel from './channel';

/* SATURATION */

function saturation ( color: string | Channels ): number {

  return channel ( color, 's' );

}

/* EXPORT */

export default saturation;
