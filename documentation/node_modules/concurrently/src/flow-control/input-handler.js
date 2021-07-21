const Rx = require('rxjs');
const { map } = require('rxjs/operators');

const defaults = require('../defaults');

module.exports = class InputHandler {
    constructor({ defaultInputTarget, inputStream, logger }) {
        this.defaultInputTarget = defaultInputTarget || defaults.defaultInputTarget;
        this.inputStream = inputStream;
        this.logger = logger;
    }

    handle(commands) {
        if (!this.inputStream) {
            return commands;
        }

        Rx.fromEvent(this.inputStream, 'data')
            .pipe(map(data => data.toString()))
            .subscribe(data => {
                let [targetId, input] = data.split(':', 2);
                targetId = input ? targetId : this.defaultInputTarget;
                input = input || data;

                const command = commands.find(command => (
                    command.name === targetId ||
                    command.index.toString() === targetId.toString()
                ));

                if (command && command.stdin) {
                    command.stdin.write(input);
                } else {
                    this.logger.logGlobalEvent(`Unable to find command ${targetId}, or it has no stdin open\n`);
                }
            });

        return commands;
    }
};
