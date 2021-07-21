'use strict';

const DIR = __dirname + '/';

const fs = require('fs');
const path = require('path');
const {promisify} = require('util');

const tryToCatch = require('try-to-catch');
const readFile = promisify(fs.readFile);

const log = require('debug')('minify');

for (const name of ['js', 'html', 'css', 'img']) {
    minify[name] = require(DIR + name);
}

module.exports = minify;

function check(name) {
    if (!name)
        throw Error('name could not be empty!');
}

async function minify(name) {
    const EXT = ['js', 'html', 'css'];
    
    check(name);
    
    const ext = path.extname(name).slice(1);
    const is = ~EXT.indexOf(ext);
    
    if (!is)
        throw Error(`File type "${ext}" not supported.`);
    
    log('optimizing ' + path.basename(name));
    return optimize(name);
}

function getName(file) {
    const notObj = typeof file !== 'object';
    
    if (notObj)
        return file;
    
    return Object.keys(file)[0];
}

/**
 * function minificate js,css and html files
 *
 * @param files     -   js, css or html file path
 */
async function optimize(file) {
    check(file);
    
    const name = getName(file);
    
    log('reading file ' + path.basename(name));
    
    const data = await readFile(name, 'utf8');
    return onDataRead(file, data);
}

/**
* Processing of files
* @param fileData {name, data}
*/
async function onDataRead(filename, data) {
    log('file ' + path.basename(filename) + ' read');
    
    const ext = path.extname(filename).replace(/^\./, '');
    
    const optimizedData = await minify[ext](data);
    
    let b64Optimize;
    
    if (ext === 'css')
        [, b64Optimize] = await tryToCatch(minify.img, filename, optimizedData);
    
    return b64Optimize || optimizedData;
}

