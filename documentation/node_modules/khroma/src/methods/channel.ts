
/* IMPORT */

import _ from '../utils';
import Channels from '../channels';
import Color from '../color';
import {CHANNEL} from '../types';

/* CHANNEL */

function channel ( color: string | Channels, channel: CHANNEL ): number {

  return _.lang.round ( Color.parse ( color )[channel] );

}

/* EXPORT */

export default channel;
