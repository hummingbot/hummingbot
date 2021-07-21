import inject from './inject/index';
import { join, relative, dirname } from 'path';
import {randomBytes} from 'crypto';
import {createFilter} from 'rollup-pluginutils';

const PROCESS_PATH = require.resolve('process-es6');
const BUFFER_PATH = require.resolve('buffer-es6');
const GLOBAL_PATH = join(__dirname, '..', 'src', 'global.js');
const BROWSER_PATH = join(__dirname, '..', 'src', 'browser.js');
const DIRNAME = '\0node-globals:dirname';
const FILENAME = '\0node-globals:filename';

function clone(obj) {
  var out = {};
  Object.keys(obj).forEach(function(key) {
    if (Array.isArray(obj[key])) {
      out[key] = obj[key].slice();
    } else {
      out[key] = obj[key];
    }
  });
  return out;
}

const getMods = options => {
  const _mods1 = {};
  const _mods2 = {};

  if (options.global !== false || options.process !== false) {
    _mods2.global = GLOBAL_PATH;
  }

  if (options.process !== false) {
    _mods1['process.nextTick'] = [PROCESS_PATH, 'nextTick'];
    _mods1['process.browser'] = [BROWSER_PATH, 'browser'];
    _mods2.process = PROCESS_PATH;
  }

  if (options.buffer !== false) {
    _mods1['Buffer.isBuffer'] = [BUFFER_PATH, 'isBuffer'];
    _mods2.Buffer = [BUFFER_PATH, 'Buffer'];
  }

  if (options.filename !== false) {
    _mods2.__filename = FILENAME;
  }

  if (options.dirname !== false) {
    _mods2.__dirname = DIRNAME;
  }

  var mods1 = new Map();
  var mods2 = new Map();

  Object.keys(_mods1).forEach(key=>{
    mods1.set(key, _mods1[key]);
  });

  Object.keys(_mods2).forEach(key=>{
    mods2.set(key, _mods2[key]);
  });

  const mods = Object.keys(_mods1).concat(Object.keys(_mods2));
  const firstpass = new RegExp(`(?:${ mods.map( escape ).join( '|')})`, 'g');

  return { mods1, mods2, firstpass };
}

const escape = ( str ) => {
  return str.replace( /[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&' );
}

export default function nodeGlobals(options) {
  options = options || {};
  const basedir = options.baseDir || '/';
  const dirs = new Map();
  const opts = clone(options);
  const exclude = (opts.exclude || []).concat(GLOBAL_PATH);
  const filter = createFilter(options.include, exclude);
  const sourceMap = options.sourceMap !== false;

  const { mods1, mods2, firstpass } = getMods(options);

  const buf = new Map();
  buf.set('global', GLOBAL_PATH);

  return {
    load(id) {
      if (dirs.has(id)) {
        return `export default '${dirs.get(id)}'`;
      }
    },
    resolveId(importee, importer) {
      if (importee === DIRNAME) {
        let id = randomBytes(15).toString('hex');
        dirs.set(id, dirname('/' + relative(basedir, importer)));
        return id;
      }
      if (importee === FILENAME) {
        let id = randomBytes(15).toString('hex');
        dirs.set(id, '/' + relative(basedir, importer));
        return id;
      }
    },
    transform(code, id) {
      if (id === BUFFER_PATH) {
        return inject(code, id, buf, new Map(), sourceMap);
      }
      if (!filter(id)) return null;
      if (code.search(firstpass) === -1) return null;
      if (id.slice(-3) !== '.js') return null;

      var out = inject(code, id, mods1, mods2, sourceMap);
      return out;
    }
  }
}
