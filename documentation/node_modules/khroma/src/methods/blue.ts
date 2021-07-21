
/* IMPORT */

import Channels from '../channels';
import channel from './channel';

/* BLUE */

function blue ( color: string | Channels ): number {

  return channel ( color, 'b' );

}

/* EXPORT */

export default blue;
