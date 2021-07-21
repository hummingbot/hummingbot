
/* IMPORT */

import Channels from '../channels';
import adjustChannel from './adjust_channel';

/* COMPLEMENT */

function complement ( color: string | Channels ): string {

  return adjustChannel ( color, 'h', 180 );

}

/* EXPORT */

export default complement;
