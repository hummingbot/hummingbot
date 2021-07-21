
/* IMPORT */

import Channels from '../channels';
import channel from './channel';

/* LIGHTNESS */

function lightness ( color: string | Channels ): number {

  return channel ( color, 'l' );

}

/* EXPORT */

export default lightness;
