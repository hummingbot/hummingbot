
/* IMPORT */

import _ from '../utils';
import Channels from '../channels';
import {TYPE} from '../types';
import Hex from './hex';
import Keyword from './keyword';
import RGB from './rgb';
import HSL from './hsl';

/* COLOR */

const Color = {

  /* VARIABLES */

  format: {
    keyword: Keyword,
    hex: Hex,
    rgb: RGB,
    rgba: RGB,
    hsl: HSL,
    hsla: HSL
  },

  /* API */

  parse: ( color: string | Channels ): Channels => {

    if ( typeof color !== 'string' ) return color;

    const channels = Hex.parse ( color ) || RGB.parse ( color ) || HSL.parse ( color ) || Keyword.parse ( color ); // Color providers ordered with performance in mind

    if ( channels ) return channels;

    throw new Error ( `Unsupported color format: "${color}"` );

  },

  stringify: ( channels: Channels ): string => {

    // SASS returns a keyword if possible, but we avoid doing that as it's slower and doesn't really add any value

    if ( !channels.changed && channels.color ) return channels.color;

    if ( channels.type.is ( TYPE.HSL ) || channels.data.r === undefined ) {

      return HSL.stringify ( channels );

    } else if ( channels.a < 1 || !Number.isInteger ( channels.r ) || !Number.isInteger ( channels.g ) || !Number.isInteger ( channels.b ) ) {

      return RGB.stringify ( channels );

    } else {

      return Hex.stringify ( channels );

    }

  }

};

/* EXPORT */

export default Color;
