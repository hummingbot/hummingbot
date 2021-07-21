module.exports = class LogExit {
    constructor({ logger }) {
        this.logger = logger;
    }

    handle(commands) {
        commands.forEach(command => command.close.subscribe(({ exitCode }) => {
            this.logger.logCommandEvent(`${command.command} exited with code ${exitCode}`, command);
        }));

        return commands;
    }
};
