
/* IMPORT */

import {describe} from 'ava-spec';
import {lighten} from '../../dist';

/* LIGHTEN */

describe ( 'lighten', it => {

  it ( 'increases the lightness channel of the color', t => {

    const tests = [
      [['hsl(0, 0%, 0%)', 0], 'hsl(0, 0%, 0%)'],
      [['hsl(0, 0%, 0%)', 50], 'hsl(0, 0%, 50%)'],
      [['hsl(0, 0%, 0%)', 75], 'hsl(0, 0%, 75%)'],
      [['hsl(0, 0%, 0%)', 100], 'hsl(0, 0%, 100%)'],
      [['hsl(0, 0%, 50%)', 100], 'hsl(0, 0%, 100%)'],
      [['hsl(0, 0%, 100%)', 100], 'hsl(0, 0%, 100%)']
    ];

    tests.forEach ( ([ args, output ]) => {
      t.is ( lighten ( ...args ), output );
    });

  });

});
