// @flow

import * as Wonka from '../../';

Wonka.pipe(
  Wonka.fromArray([1, 2, 3]),
  Wonka.map(x => x * 2),
  Wonka.publish
);
