
/* IMPORT */

import Channels from '../channels';
import Color from '../color';
import rgba from './rgba';

/* MIX */

//SOURCE: https://github.com/sass/dart-sass/blob/7457d2e9e7e623d9844ffd037a070cf32d39c348/lib/src/functions/color.dart#L718-L756

function mix ( color1: string | Channels, color2: string | Channels, weight: number = 50 ): string {

  const {r: r1, g: g1, b: b1, a: a1} = Color.parse ( color1 ),
        {r: r2, g: g2, b: b2, a: a2} = Color.parse ( color2 ),
        weightScale = weight / 100,
        weightNormalized = ( weightScale * 2 ) - 1,
        alphaDelta = a1 - a2,
        weight1combined = ( ( weightNormalized * alphaDelta ) === -1 ) ? weightNormalized : ( weightNormalized + alphaDelta ) / ( 1 + weightNormalized * alphaDelta ),
        weight1 = ( weight1combined + 1 ) / 2,
        weight2 = 1 - weight1,
        r = ( r1 * weight1 ) + ( r2 * weight2 ),
        g = ( g1 * weight1 ) + ( g2 * weight2 ),
        b = ( b1 * weight1 ) + ( b2 * weight2 ),
        a = ( a1 * weightScale ) + ( a2 * ( 1 - weightScale ) );

  return rgba ( r, g, b, a );

}

/* EXPORT */

export default mix;
