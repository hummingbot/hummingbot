
/* IMPORT */

import {describe} from 'ava-spec';
import {transparentize} from '../../dist';

/* TRANSPARENTIZE */

describe ( 'transparentize', it => {

  it ( 'decreases the opacity channel of the color', t => {

    const tests = [
      [['#000000', 1], 'rgba(0, 0, 0, 0)'],
      [['rgba(0, 0, 0, 0.5)', 0.5], 'rgba(0, 0, 0, 0)'],
      [['rgba(0, 0, 0, 0.5)', 1], 'rgba(0, 0, 0, 0)'],
      [['rgba(0, 0, 0, 0.5)', 0.1], 'rgba(0, 0, 0, 0.4)']
    ];

    tests.forEach ( ([ args, output ]) => {
      t.is ( transparentize ( ...args ), output );
    });

  });

});
