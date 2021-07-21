"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const child_process_1 = require("child_process");
const tmp_1 = tslib_1.__importDefault(require("tmp"));
const debug_1 = tslib_1.__importDefault(require("debug"));
const path_1 = tslib_1.__importDefault(require("path"));
const sudo_prompt_1 = tslib_1.__importDefault(require("sudo-prompt"));
const constants_1 = require("./constants");
const debug = debug_1.default('devcert:util');
function openssl(args) {
    return run('openssl', args, {
        stdio: 'pipe',
        env: Object.assign({
            RANDFILE: path_1.default.join(constants_1.configPath('.rnd'))
        }, process.env)
    });
}
exports.openssl = openssl;
function run(cmd, args, options = {}) {
    debug(`execFileSync: \`${cmd} ${args.join(' ')}\``);
    return child_process_1.execFileSync(cmd, args, options);
}
exports.run = run;
function sudoAppend(file, input) {
    run('sudo', ['tee', '-a', file], {
        input
    });
}
exports.sudoAppend = sudoAppend;
function waitForUser() {
    return new Promise((resolve) => {
        process.stdin.resume();
        process.stdin.on('data', resolve);
    });
}
exports.waitForUser = waitForUser;
function reportableError(message) {
    return new Error(`${message} | This is a bug in devcert, please report the issue at https://github.com/davewasmer/devcert/issues`);
}
exports.reportableError = reportableError;
function mktmp() {
    // discardDescriptor because windows complains the file is in use if we create a tmp file
    // and then shell out to a process that tries to use it
    return tmp_1.default.fileSync({ discardDescriptor: true }).name;
}
exports.mktmp = mktmp;
function sudo(cmd) {
    return new Promise((resolve, reject) => {
        sudo_prompt_1.default.exec(cmd, { name: 'devcert' }, (err, stdout, stderr) => {
            let error = err || (typeof stderr === 'string' && stderr.trim().length > 0 && new Error(stderr));
            error ? reject(error) : resolve(stdout);
        });
    });
}
exports.sudo = sudo;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXRpbHMuanMiLCJzb3VyY2VSb290IjoiL1VzZXJzL2p6ZXRsZW4vZ2l0cy9kZXZjZXJ0LyIsInNvdXJjZXMiOlsidXRpbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsaURBQWtFO0FBQ2xFLHNEQUFzQjtBQUN0QiwwREFBZ0M7QUFDaEMsd0RBQXdCO0FBQ3hCLHNFQUFxQztBQUVyQywyQ0FBeUM7QUFFekMsTUFBTSxLQUFLLEdBQUcsZUFBVyxDQUFDLGNBQWMsQ0FBQyxDQUFDO0FBRTFDLGlCQUF3QixJQUFjO0lBQ3BDLE9BQU8sR0FBRyxDQUFDLFNBQVMsRUFBRSxJQUFJLEVBQUU7UUFDMUIsS0FBSyxFQUFFLE1BQU07UUFDYixHQUFHLEVBQUUsTUFBTSxDQUFDLE1BQU0sQ0FBQztZQUNqQixRQUFRLEVBQUUsY0FBSSxDQUFDLElBQUksQ0FBQyxzQkFBVSxDQUFDLE1BQU0sQ0FBQyxDQUFDO1NBQ3hDLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQztLQUNoQixDQUFDLENBQUM7QUFDTCxDQUFDO0FBUEQsMEJBT0M7QUFFRCxhQUFvQixHQUFXLEVBQUUsSUFBYyxFQUFFLFVBQStCLEVBQUU7SUFDaEYsS0FBSyxDQUFDLG1CQUFvQixHQUFJLElBQUksSUFBSSxDQUFDLElBQUksQ0FBQyxHQUFHLENBQUMsSUFBSSxDQUFDLENBQUM7SUFDdEQsT0FBTyw0QkFBWSxDQUFDLEdBQUcsRUFBRSxJQUFJLEVBQUUsT0FBTyxDQUFDLENBQUM7QUFDMUMsQ0FBQztBQUhELGtCQUdDO0FBRUQsb0JBQTJCLElBQVksRUFBRSxLQUFtQztJQUMxRSxHQUFHLENBQUMsTUFBTSxFQUFFLENBQUMsS0FBSyxFQUFFLElBQUksRUFBRSxJQUFJLENBQUMsRUFBRTtRQUMvQixLQUFLO0tBQ04sQ0FBQyxDQUFDO0FBQ0wsQ0FBQztBQUpELGdDQUlDO0FBRUQ7SUFDRSxPQUFPLElBQUksT0FBTyxDQUFDLENBQUMsT0FBTyxFQUFFLEVBQUU7UUFDN0IsT0FBTyxDQUFDLEtBQUssQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUN2QixPQUFPLENBQUMsS0FBSyxDQUFDLEVBQUUsQ0FBQyxNQUFNLEVBQUUsT0FBTyxDQUFDLENBQUM7SUFDcEMsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDO0FBTEQsa0NBS0M7QUFFRCx5QkFBZ0MsT0FBZTtJQUM3QyxPQUFPLElBQUksS0FBSyxDQUFDLEdBQUcsT0FBTyxzR0FBc0csQ0FBQyxDQUFDO0FBQ3JJLENBQUM7QUFGRCwwQ0FFQztBQUVEO0lBQ0UseUZBQXlGO0lBQ3pGLHVEQUF1RDtJQUN2RCxPQUFPLGFBQUcsQ0FBQyxRQUFRLENBQUMsRUFBRSxpQkFBaUIsRUFBRSxJQUFJLEVBQUUsQ0FBQyxDQUFDLElBQUksQ0FBQztBQUN4RCxDQUFDO0FBSkQsc0JBSUM7QUFFRCxjQUFxQixHQUFXO0lBQzlCLE9BQU8sSUFBSSxPQUFPLENBQUMsQ0FBQyxPQUFPLEVBQUUsTUFBTSxFQUFFLEVBQUU7UUFDckMscUJBQVUsQ0FBQyxJQUFJLENBQUMsR0FBRyxFQUFFLEVBQUUsSUFBSSxFQUFFLFNBQVMsRUFBRSxFQUFFLENBQUMsR0FBaUIsRUFBRSxNQUFxQixFQUFFLE1BQXFCLEVBQUUsRUFBRTtZQUM1RyxJQUFJLEtBQUssR0FBRyxHQUFHLElBQUksQ0FBQyxPQUFPLE1BQU0sS0FBSyxRQUFRLElBQUksTUFBTSxDQUFDLElBQUksRUFBRSxDQUFDLE1BQU0sR0FBRyxDQUFDLElBQUksSUFBSSxLQUFLLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBRTtZQUNsRyxLQUFLLENBQUMsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxDQUFDLENBQUMsT0FBTyxDQUFDLE1BQU0sQ0FBQyxDQUFDO1FBQzFDLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDO0FBUEQsb0JBT0MiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBleGVjRmlsZVN5bmMsIEV4ZWNGaWxlU3luY09wdGlvbnMgfSBmcm9tICdjaGlsZF9wcm9jZXNzJztcbmltcG9ydCB0bXAgZnJvbSAndG1wJztcbmltcG9ydCBjcmVhdGVEZWJ1ZyBmcm9tICdkZWJ1Zyc7XG5pbXBvcnQgcGF0aCBmcm9tICdwYXRoJztcbmltcG9ydCBzdWRvUHJvbXB0IGZyb20gJ3N1ZG8tcHJvbXB0JztcblxuaW1wb3J0IHsgY29uZmlnUGF0aCB9IGZyb20gJy4vY29uc3RhbnRzJztcblxuY29uc3QgZGVidWcgPSBjcmVhdGVEZWJ1ZygnZGV2Y2VydDp1dGlsJyk7XG5cbmV4cG9ydCBmdW5jdGlvbiBvcGVuc3NsKGFyZ3M6IHN0cmluZ1tdKSB7XG4gIHJldHVybiBydW4oJ29wZW5zc2wnLCBhcmdzLCB7XG4gICAgc3RkaW86ICdwaXBlJyxcbiAgICBlbnY6IE9iamVjdC5hc3NpZ24oe1xuICAgICAgUkFOREZJTEU6IHBhdGguam9pbihjb25maWdQYXRoKCcucm5kJykpXG4gICAgfSwgcHJvY2Vzcy5lbnYpXG4gIH0pO1xufVxuXG5leHBvcnQgZnVuY3Rpb24gcnVuKGNtZDogc3RyaW5nLCBhcmdzOiBzdHJpbmdbXSwgb3B0aW9uczogRXhlY0ZpbGVTeW5jT3B0aW9ucyA9IHt9KSB7XG4gIGRlYnVnKGBleGVjRmlsZVN5bmM6IFxcYCR7IGNtZCB9ICR7YXJncy5qb2luKCcgJyl9XFxgYCk7XG4gIHJldHVybiBleGVjRmlsZVN5bmMoY21kLCBhcmdzLCBvcHRpb25zKTtcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIHN1ZG9BcHBlbmQoZmlsZTogc3RyaW5nLCBpbnB1dDogRXhlY0ZpbGVTeW5jT3B0aW9uc1tcImlucHV0XCJdKSB7XG4gIHJ1bignc3VkbycsIFsndGVlJywgJy1hJywgZmlsZV0sIHtcbiAgICBpbnB1dFxuICB9KTtcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIHdhaXRGb3JVc2VyKCkge1xuICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUpID0+IHtcbiAgICBwcm9jZXNzLnN0ZGluLnJlc3VtZSgpO1xuICAgIHByb2Nlc3Muc3RkaW4ub24oJ2RhdGEnLCByZXNvbHZlKTtcbiAgfSk7XG59XG5cbmV4cG9ydCBmdW5jdGlvbiByZXBvcnRhYmxlRXJyb3IobWVzc2FnZTogc3RyaW5nKSB7XG4gIHJldHVybiBuZXcgRXJyb3IoYCR7bWVzc2FnZX0gfCBUaGlzIGlzIGEgYnVnIGluIGRldmNlcnQsIHBsZWFzZSByZXBvcnQgdGhlIGlzc3VlIGF0IGh0dHBzOi8vZ2l0aHViLmNvbS9kYXZld2FzbWVyL2RldmNlcnQvaXNzdWVzYCk7XG59XG5cbmV4cG9ydCBmdW5jdGlvbiBta3RtcCgpIHtcbiAgLy8gZGlzY2FyZERlc2NyaXB0b3IgYmVjYXVzZSB3aW5kb3dzIGNvbXBsYWlucyB0aGUgZmlsZSBpcyBpbiB1c2UgaWYgd2UgY3JlYXRlIGEgdG1wIGZpbGVcbiAgLy8gYW5kIHRoZW4gc2hlbGwgb3V0IHRvIGEgcHJvY2VzcyB0aGF0IHRyaWVzIHRvIHVzZSBpdFxuICByZXR1cm4gdG1wLmZpbGVTeW5jKHsgZGlzY2FyZERlc2NyaXB0b3I6IHRydWUgfSkubmFtZTtcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIHN1ZG8oY21kOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZyB8IG51bGw+IHtcbiAgcmV0dXJuIG5ldyBQcm9taXNlKChyZXNvbHZlLCByZWplY3QpID0+IHtcbiAgICBzdWRvUHJvbXB0LmV4ZWMoY21kLCB7IG5hbWU6ICdkZXZjZXJ0JyB9LCAoZXJyOiBFcnJvciB8IG51bGwsIHN0ZG91dDogc3RyaW5nIHwgbnVsbCwgc3RkZXJyOiBzdHJpbmcgfCBudWxsKSA9PiB7XG4gICAgICBsZXQgZXJyb3IgPSBlcnIgfHwgKHR5cGVvZiBzdGRlcnIgPT09ICdzdHJpbmcnICYmIHN0ZGVyci50cmltKCkubGVuZ3RoID4gMCAmJiBuZXcgRXJyb3Ioc3RkZXJyKSkgO1xuICAgICAgZXJyb3IgPyByZWplY3QoZXJyb3IpIDogcmVzb2x2ZShzdGRvdXQpO1xuICAgIH0pO1xuICB9KTtcbn1cbiJdfQ==