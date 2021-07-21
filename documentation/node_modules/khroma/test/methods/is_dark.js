
/* IMPORT */

import {describe} from 'ava-spec';
import {isDark} from '../../dist';

/* IS DARK */

describe ( 'isDark', it => {

  it ( 'checks if the provided color is a dark color', t => {

    const tests = [
      ['#000000', true],
      ['#8a8a8a', true],
      ['#bbbbbb', true],
      ['#ffcc00', false],
      ['#e0e0e0', false],
      ['#ffffff', false]
    ];

    tests.forEach ( ([ color, output ]) => {
      t.is ( isDark ( color ), output );
    });

  });

});
