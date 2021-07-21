
/* IMPORT */

import _ from '../utils';
import Channels from '../channels';
import Color from '../color';

/* LUMINANCE */

//SOURCE: https://planetcalc.com/7779

function luminance ( color: string | Channels ): number {

  const {r, g, b} = Color.parse ( color ),
        luminance = .2126 * _.channel.toLinear ( r ) + .7152 * _.channel.toLinear ( g ) + .0722 * _.channel.toLinear ( b );

  return _.lang.round ( luminance );

}

/* EXPORT */

export default luminance;
