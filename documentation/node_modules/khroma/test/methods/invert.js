
/* IMPORT */

import {describe} from 'ava-spec';
import {invert} from '../../dist';

/* INVERT */

describe ( 'invert', it => {

  it ( 'gets the inverse of the color', t => {

    const tests = [
      [['#b37399'], '#4c8c66'],
      [['black'], '#ffffff'],
      [['#550e0c', 20 ], 'rgb(102, 59.4, 58.2)']
    ];

    tests.forEach ( ([ args, output ]) => {
      t.is ( invert ( ...args ), output );
    });

  });

});
