
/* IMPORT */

import _ from '../utils';
import Channels from '../channels';
import Color from '../color';
import {CHANNELS} from '../types';

/* CHANGE */

function change ( color: string | Channels, channels: Partial<CHANNELS> ): string {

  const ch = Color.parse ( color );

  for ( const c in channels ) {

    ch[c] = _.channel.clamp[c]( channels[c] );

  }

  return Color.stringify ( ch );

}

/* EXPORT */

export default change;
