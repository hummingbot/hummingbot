'use strict';

// requiring ses exposes "lockdown" on the global
require('ses');

/*
 * lockdown freezes the primordials
 * disabling the error taming makes debugging much easier
 * lockdown({ errorTaming: 'unsafe' });
 */
// eslint-disable-next-line no-undef
lockdown();

// initialize the module
require('..');
