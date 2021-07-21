
/* IMPORT */

import _ from '../utils';
import Channels from '../channels';
import Color from '../color';
import {CHANNEL} from '../types';

/* ADJUST CHANNEL */

function adjustChannel ( color: string | Channels, channel: CHANNEL, amount: number ): string {

  const channels = Color.parse ( color ),
        amountCurrent = channels[channel],
        amountNext = _.channel.clamp[channel]( amountCurrent + amount );

  if ( amountCurrent !== amountNext ) channels[channel] = amountNext;

  return Color.stringify ( channels );

}

/* EXPORT */

export default adjustChannel;
