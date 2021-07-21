
/* IMPORT */

import Channels from '../channels';
import isLight from './is_light';

/* IS DARK */

function isDark ( color: string | Channels ): boolean {

  return !isLight ( color );

}

/* EXPORT */

export default isDark;
