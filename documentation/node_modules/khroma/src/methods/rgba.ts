
/* IMPORT */

import _ from '../utils';
import Channels from '../channels';
import ChannelsReusable from '../channels/reusable';
import Color from '../color';
import change from './change';

/* RGBA */

function rgba ( color: string | Channels, opacity: number ): string;
function rgba ( r: number, g: number, b: number, a: number ): string;
function rgba ( r: string | Channels | number, g: number, b: number = 0, a: number = 1 ): string {  //TSC: `b` shouldn't have a default value

  if ( typeof r !== 'number' ) return change ( r, { a: g } );

  const channels = ChannelsReusable.set ({
    r: _.channel.clamp.r ( r ),
    g: _.channel.clamp.g ( g ),
    b: _.channel.clamp.b ( b ),
    a: _.channel.clamp.a ( a )
  });

  return Color.stringify ( channels );

}

/* EXPORT */

export default rgba;
