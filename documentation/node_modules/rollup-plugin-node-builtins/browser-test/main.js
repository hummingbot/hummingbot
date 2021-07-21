import {get} from 'http';
import {createContext, runInContext} from 'vm';
import {equal, deepEqual} from 'assert';

get('foo.json', function (res) {
  console.log('status', res.statusCode);
  var data = '';
  res.on('data', function (d) {
    data += d.toString();
  }).on('error', function (e) {
    console.log('error', e);
  }).on('end', function () {
    console.log(data);
    if (global.document) {
      afterMain();
    } else {
      afterWorker();
    }
  });
})
function afterMain() {
  var context = createContext();

  runInContext('var x = 1', context);
  deepEqual(context, { x: 1 });

  runInContext('var y = 2;', context);
  var x = runInContext('++x', context);
  equal(x, 2);
  equal(context.x, 2);
  equal(context.x, context.y);
  console.log('ok main');
}
function afterWorker() {
  var context = createContext({x: 0});

  runInContext('x++', context);
  deepEqual(context, { x: 1 });

  var x = runInContext('++x', context);
  equal(x, 2);
  equal(context.x, 2);
  console.log('ok worker');
}
