const { createMockInstance } = require('jest-create-mock-instance');
const { Writable } = require('stream');
const { Subject } = require('rxjs');

module.exports = (name = 'foo', command = 'echo foo', index = 0) => ({
    index,
    name,
    command,
    close: new Subject(),
    error: new Subject(),
    stderr: new Subject(),
    stdout: new Subject(),
    stdin: createMockInstance(Writable),
    start: jest.fn(),
    kill: jest.fn()
});
