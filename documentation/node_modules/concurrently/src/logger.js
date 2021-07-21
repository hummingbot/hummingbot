const chalk = require('chalk');
const _ = require('lodash');
const formatDate = require('date-fns/format');

const defaults = require('./defaults');

module.exports = class Logger {
    constructor({ outputStream, prefixFormat, prefixLength, raw, timestampFormat }) {
        this.raw = raw;
        this.outputStream = outputStream;
        this.prefixFormat = prefixFormat;
        this.prefixLength = prefixLength || defaults.prefixLength;
        this.timestampFormat = timestampFormat || defaults.timestampFormat;
    }

    shortenText(text) {
        if (!text || text.length <= this.prefixLength) {
            return text;
        }

        const ellipsis = '..';
        const prefixLength = this.prefixLength - ellipsis.length;
        const endLength = Math.floor(prefixLength / 2);
        const beginningLength = prefixLength - endLength;

        const beginnning = text.substring(0, beginningLength);
        const end = text.substring(text.length - endLength, text.length);
        return beginnning + ellipsis + end;
    }

    getPrefixesFor(command) {
        return {
            none: '',
            pid: command.pid,
            index: command.index,
            name: command.name,
            command: this.shortenText(command.command),
            time: formatDate(Date.now(), this.timestampFormat)
        };
    }

    getPrefix(command) {
        const prefix = this.prefixFormat || (command.name ? 'name' : 'index');
        if (prefix === 'none') {
            return '';
        }

        const prefixes = this.getPrefixesFor(command);
        if (Object.keys(prefixes).includes(prefix)) {
            return `[${prefixes[prefix]}]`;
        }

        return _.reduce(prefixes, (prev, val, key) => {
            const keyRegex = new RegExp(_.escapeRegExp(`{${key}}`), 'g');
            return prev.replace(keyRegex, val);
        }, prefix);
    }

    colorText(command, text) {
        const color = _.get(chalk, command.prefixColor, chalk.gray.dim);
        return color(text);
    }

    logCommandEvent(text, command) {
        if (this.raw) {
            return;
        }

        this.logCommandText(chalk.gray.dim(text) + '\n', command);
    }

    logCommandText(text, command) {
        const prefix = this.colorText(command, this.getPrefix(command));
        return this.log(prefix + (prefix ? ' ' : ''), text);
    }

    logGlobalEvent(text) {
        if (this.raw) {
            return;
        }

        this.log(chalk.gray.dim('-->') + ' ', chalk.gray.dim(text) + '\n');
    }

    log(prefix, text) {
        if (this.raw) {
            return this.outputStream.write(text);
        }

        // #70 - replace some ANSI code that would impact clearing lines
        text = text.replace(/\u2026/g, '...');

        const lines = text.split('\n').map((line, index, lines) => {
            // First line will write prefix only if we finished the last write with a LF.
            // Last line won't write prefix because it should be empty.
            if (index === 0 || index === lines.length - 1) {
                return line;
            }
            return prefix + line;
        });

        if (!this.lastChar || this.lastChar === '\n') {
            this.outputStream.write(prefix);
        }

        this.lastChar = text[text.length - 1];
        this.outputStream.write(lines.join('\n'));
    }
};
