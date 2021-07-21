
/* IMPORT */

import {describe} from 'ava-spec';
import {hue} from '../../dist';

/* HUE */

describe ( 'hue', it => {

  it ( 'gets the hue channel of the color', t => {

    const tests = [
      ['hsl(10, 20%, 30%)', 10],
      ['rgb(10, 20, 30)', 210],
      ['#102030', 210]
    ];

    tests.forEach ( ([ color, output ]) => {
      t.is ( hue ( color ), output );
    });

  });

});
