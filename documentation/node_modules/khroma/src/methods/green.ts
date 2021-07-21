
/* IMPORT */

import Channels from '../channels';
import channel from './channel';

/* GREEN */

function green ( color: string | Channels ): number {

  return channel ( color, 'g' );

}

/* EXPORT */

export default green;
