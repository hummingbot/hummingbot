// MIT lisence
// from https://github.com/substack/tty-browserify/blob/1ba769a6429d242f36226538835b4034bf6b7886/index.js

export function isatty() {
  return false;
}

export function ReadStream() {
  throw new Error('tty.ReadStream is not implemented');
}

export function WriteStream() {
  throw new Error('tty.ReadStream is not implemented');
}

export default {
  isatty: isatty,
  ReadStream: ReadStream,
  WriteStream: WriteStream
}
