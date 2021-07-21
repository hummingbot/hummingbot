const { of } = require('rxjs');

module.exports = class LogExit {
    constructor({ logger }) {
        this.logger = logger;
    }

    handle(commands) {
        commands.forEach(command => command.error.subscribe(event => {
            this.logger.logCommandEvent(
                `Error occurred when executing command: ${command.command}`,
                command
            );

            this.logger.logCommandEvent(event.stack || event, command);
        }));

        return commands;
    }
};
