
/* IMPORT */

import _ from '../utils';
import Channels from '../channels';
import Color from '../color';
import {CHANNELS} from '../types';
import adjust from './adjust';

/* SCALE */

function scale ( color: string | Channels, channels: Partial<CHANNELS> ): string {

  const ch = Color.parse ( color ),
        adjustments: Partial<CHANNELS> = {},
        delta = ( amount: number, weight: number, max: number ) => weight > 0 ? ( max - amount ) * weight / 100 : amount * weight / 100;

  for ( const c in channels ) {

    adjustments[c] = delta ( ch[c], channels[c], _.channel.max[c] );

  }

  return adjust ( color, adjustments );

}

/* EXPORT */

export default scale;
