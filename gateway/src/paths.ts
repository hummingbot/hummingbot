import path from 'path';
import fs from 'fs';

/**
 * Returns the project root path.
 *
 * This can be different depending on whether compiled scripts (i.e. in dist/)
 * are used, or, in jest's case, whether the .ts files are being run directly
 * via ts-jest.
 */
export function rootPath(): string {
  const insideDistDir: boolean = __filename.match(/dist\//) !== null;
  if (insideDistDir) {
    return fs.realpathSync(path.join(__dirname, '../../'), 'utf8');
  }
  return fs.realpathSync(path.join(__dirname, '../'), 'utf8');
}
