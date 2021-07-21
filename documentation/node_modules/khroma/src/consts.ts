
/* IMPORT */

import _ from './utils';

/* CONSTS */

const DEC2HEX = {};

for ( let i = 0; i <= 255; i++ ) DEC2HEX[i] = _.unit.dec2hex ( i ); // Populating dynamically, striking a balance between code size and performance

/* EXPORT */

export {DEC2HEX};
