"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const path_1 = tslib_1.__importDefault(require("path"));
const url_1 = tslib_1.__importDefault(require("url"));
const debug_1 = tslib_1.__importDefault(require("debug"));
const assert_1 = tslib_1.__importDefault(require("assert"));
const get_port_1 = tslib_1.__importDefault(require("get-port"));
const http_1 = tslib_1.__importDefault(require("http"));
const glob_1 = require("glob");
const fs_1 = require("fs");
const utils_1 = require("../utils");
const constants_1 = require("../constants");
const user_interface_1 = tslib_1.__importDefault(require("../user-interface"));
const child_process_1 = require("child_process");
const debug = debug_1.default('devcert:platforms:shared');
/**
 *  Given a directory or glob pattern of directories, run a callback for each db
 *  directory, with a version argument.
 */
function doForNSSCertDB(nssDirGlob, callback) {
    glob_1.sync(nssDirGlob).forEach((potentialNSSDBDir) => {
        debug(`checking to see if ${potentialNSSDBDir} is a valid NSS database directory`);
        if (fs_1.existsSync(path_1.default.join(potentialNSSDBDir, 'cert8.db'))) {
            debug(`Found legacy NSS database in ${potentialNSSDBDir}, running callback...`);
            callback(potentialNSSDBDir, 'legacy');
        }
        if (fs_1.existsSync(path_1.default.join(potentialNSSDBDir, 'cert9.db'))) {
            debug(`Found modern NSS database in ${potentialNSSDBDir}, running callback...`);
            callback(potentialNSSDBDir, 'modern');
        }
    });
}
/**
 *  Given a directory or glob pattern of directories, attempt to install the
 *  CA certificate to each directory containing an NSS database.
 */
function addCertificateToNSSCertDB(nssDirGlob, certPath, certutilPath) {
    debug(`trying to install certificate into NSS databases in ${nssDirGlob}`);
    doForNSSCertDB(nssDirGlob, (dir, version) => {
        const dirArg = version === 'modern' ? `sql:${dir}` : dir;
        utils_1.run(certutilPath, ['-A', '-d', dirArg, '-t', 'C,,', '-i', certPath, '-n', 'devcert']);
    });
    debug(`finished scanning & installing certificate in NSS databases in ${nssDirGlob}`);
}
exports.addCertificateToNSSCertDB = addCertificateToNSSCertDB;
function removeCertificateFromNSSCertDB(nssDirGlob, certPath, certutilPath) {
    debug(`trying to remove certificates from NSS databases in ${nssDirGlob}`);
    doForNSSCertDB(nssDirGlob, (dir, version) => {
        const dirArg = version === 'modern' ? `sql:${dir}` : dir;
        try {
            utils_1.run(certutilPath, ['-A', '-d', dirArg, '-t', 'C,,', '-i', certPath, '-n', 'devcert']);
        }
        catch (e) {
            debug(`failed to remove ${certPath} from ${dir}, continuing. ${e.toString()}`);
        }
    });
    debug(`finished scanning & installing certificate in NSS databases in ${nssDirGlob}`);
}
exports.removeCertificateFromNSSCertDB = removeCertificateFromNSSCertDB;
/**
 *  Check to see if Firefox is still running, and if so, ask the user to close
 *  it. Poll until it's closed, then return.
 *
 * This is needed because Firefox appears to load the NSS database in-memory on
 * startup, and overwrite on exit. So we have to ask the user to quite Firefox
 * first so our changes don't get overwritten.
 */
function closeFirefox() {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        if (isFirefoxOpen()) {
            yield user_interface_1.default.closeFirefoxBeforeContinuing();
            while (isFirefoxOpen()) {
                yield sleep(50);
            }
        }
    });
}
exports.closeFirefox = closeFirefox;
/**
 * Check if Firefox is currently open
 */
function isFirefoxOpen() {
    // NOTE: We use some Windows-unfriendly methods here (ps) because Windows
    // never needs to check this, because it doesn't update the NSS DB
    // automaticaly.
    assert_1.default(constants_1.isMac || constants_1.isLinux, 'checkForOpenFirefox was invoked on a platform other than Mac or Linux');
    return child_process_1.execSync('ps aux').indexOf('firefox') > -1;
}
function sleep(ms) {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        return new Promise((resolve) => setTimeout(resolve, ms));
    });
}
/**
 * Firefox manages it's own trust store for SSL certificates, which can be
 * managed via the certutil command (supplied by NSS tooling packages). In the
 * event that certutil is not already installed, and either can't be installed
 * (Windows) or the user doesn't want to install it (skipCertutilInstall:
 * true), it means that we can't programmatically tell Firefox to trust our
 * root CA certificate.
 *
 * There is a recourse though. When a Firefox tab is directed to a URL that
 * responds with a certificate, it will automatically prompt the user if they
 * want to add it to their trusted certificates. So if we can't automatically
 * install the certificate via certutil, we instead start a quick web server
 * and host our certificate file. Then we open the hosted cert URL in Firefox
 * to kick off the GUI flow.
 *
 * This method does all this, along with providing user prompts in the terminal
 * to walk them through this process.
 */
function openCertificateInFirefox(firefoxPath, certPath) {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        debug('Adding devert to Firefox trust stores manually. Launching a webserver to host our certificate temporarily ...');
        let port = yield get_port_1.default();
        let server = http_1.default.createServer((req, res) => tslib_1.__awaiter(this, void 0, void 0, function* () {
            let { pathname } = url_1.default.parse(req.url);
            if (pathname === '/certificate') {
                res.writeHead(200, { 'Content-type': 'application/x-x509-ca-cert' });
                res.write(fs_1.readFileSync(certPath));
                res.end();
            }
            else {
                res.writeHead(200);
                res.write(yield user_interface_1.default.firefoxWizardPromptPage(`http://localhost:${port}/certificate`));
                res.end();
            }
        })).listen(port);
        debug('Certificate server is up. Printing instructions for user and launching Firefox with hosted certificate URL');
        yield user_interface_1.default.startFirefoxWizard(`http://localhost:${port}`);
        utils_1.run(firefoxPath, [`http://localhost:${port}`]);
        yield user_interface_1.default.waitForFirefoxWizard();
        server.close();
    });
}
exports.openCertificateInFirefox = openCertificateInFirefox;
function assertNotTouchingFiles(filepath, operation) {
    if (!filepath.startsWith(constants_1.configDir) && !filepath.startsWith(constants_1.getLegacyConfigDir())) {
        throw new Error(`Devcert cannot ${operation} ${filepath}; it is outside known devcert config directories!`);
    }
}
exports.assertNotTouchingFiles = assertNotTouchingFiles;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2hhcmVkLmpzIiwic291cmNlUm9vdCI6Ii9Vc2Vycy9qemV0bGVuL2dpdHMvZGV2Y2VydC8iLCJzb3VyY2VzIjpbInBsYXRmb3Jtcy9zaGFyZWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsd0RBQXdCO0FBQ3hCLHNEQUFzQjtBQUN0QiwwREFBZ0M7QUFDaEMsNERBQTRCO0FBQzVCLGdFQUErQjtBQUMvQix3REFBd0I7QUFDeEIsK0JBQW9DO0FBQ3BDLDJCQUFvRTtBQUNwRSxvQ0FBK0I7QUFDL0IsNENBQThFO0FBQzlFLCtFQUFtQztBQUNuQyxpREFBaUQ7QUFFakQsTUFBTSxLQUFLLEdBQUcsZUFBVyxDQUFDLDBCQUEwQixDQUFDLENBQUM7QUFFdEQ7OztHQUdHO0FBQ0gsd0JBQXdCLFVBQWtCLEVBQUUsUUFBNkQ7SUFDdkcsV0FBSSxDQUFDLFVBQVUsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxDQUFDLGlCQUFpQixFQUFFLEVBQUU7UUFDN0MsS0FBSyxDQUFDLHNCQUF1QixpQkFBa0Isb0NBQW9DLENBQUMsQ0FBQztRQUNyRixJQUFJLGVBQU0sQ0FBQyxjQUFJLENBQUMsSUFBSSxDQUFDLGlCQUFpQixFQUFFLFVBQVUsQ0FBQyxDQUFDLEVBQUU7WUFDcEQsS0FBSyxDQUFDLGdDQUFpQyxpQkFBa0IsdUJBQXVCLENBQUMsQ0FBQTtZQUNqRixRQUFRLENBQUMsaUJBQWlCLEVBQUUsUUFBUSxDQUFDLENBQUM7U0FDdkM7UUFDRCxJQUFJLGVBQU0sQ0FBQyxjQUFJLENBQUMsSUFBSSxDQUFDLGlCQUFpQixFQUFFLFVBQVUsQ0FBQyxDQUFDLEVBQUU7WUFDcEQsS0FBSyxDQUFDLGdDQUFpQyxpQkFBa0IsdUJBQXVCLENBQUMsQ0FBQTtZQUNqRixRQUFRLENBQUMsaUJBQWlCLEVBQUUsUUFBUSxDQUFDLENBQUM7U0FDdkM7SUFDSCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUM7QUFFRDs7O0dBR0c7QUFDSCxtQ0FBMEMsVUFBa0IsRUFBRSxRQUFnQixF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b20gJ3BhdGgnO1xuaW1wb3J0IHVybCBmcm9tICd1cmwnO1xuaW1wb3J0IGNyZWF0ZURlYnVnIGZyb20gJ2RlYnVnJztcbmltcG9ydCBhc3NlcnQgZnJvbSAnYXNzZXJ0JztcbmltcG9ydCBnZXRQb3J0IGZyb20gJ2dldC1wb3J0JztcbmltcG9ydCBodHRwIGZyb20gJ2h0dHAnO1xuaW1wb3J0IHsgc3luYyBhcyBnbG9iIH0gZnJvbSAnZ2xvYic7XG5pbXBvcnQgeyByZWFkRmlsZVN5bmMgYXMgcmVhZEZpbGUsIGV4aXN0c1N5bmMgYXMgZXhpc3RzIH0gZnJvbSAnZnMnO1xuaW1wb3J0IHsgcnVuIH0gZnJvbSAnLi4vdXRpbHMnO1xuaW1wb3J0IHsgaXNNYWMsIGlzTGludXggLCBjb25maWdEaXIsIGdldExlZ2FjeUNvbmZpZ0RpciB9IGZyb20gJy4uL2NvbnN0YW50cyc7XG5pbXBvcnQgVUkgZnJvbSAnLi4vdXNlci1pbnRlcmZhY2UnO1xuaW1wb3J0IHsgZXhlY1N5bmMgYXMgZXhlYyB9IGZyb20gJ2NoaWxkX3Byb2Nlc3MnO1xuXG5jb25zdCBkZWJ1ZyA9IGNyZWF0ZURlYnVnKCdkZXZjZXJ0OnBsYXRmb3JtczpzaGFyZWQnKTtcblxuLyoqXG4gKiAgR2l2ZW4gYSBkaXJlY3Rvcnkgb3IgZ2xvYiBwYXR0ZXJuIG9mIGRpcmVjdG9yaWVzLCBydW4gYSBjYWxsYmFjayBmb3IgZWFjaCBkYlxuICogIGRpcmVjdG9yeSwgd2l0aCBhIHZlcnNpb24gYXJndW1lbnQuXG4gKi9cbmZ1bmN0aW9uIGRvRm9yTlNTQ2VydERCKG5zc0Rpckdsb2I6IHN0cmluZywgY2FsbGJhY2s6IChkaXI6IHN0cmluZywgdmVyc2lvbjogXCJsZWdhY3lcIiB8IFwibW9kZXJuXCIpID0+IHZvaWQpOiB2b2lkIHtcbiAgZ2xvYihuc3NEaXJHbG9iKS5mb3JFYWNoKChwb3RlbnRpYWxOU1NEQkRpcikgPT4ge1xuICAgIGRlYnVnKGBjaGVja2luZyB0byBzZWUgaWYgJHsgcG90ZW50aWFsTlNTREJEaXIgfSBpcyBhIHZhbGlkIE5TUyBkYXRhYmFzZSBkaXJlY3RvcnlgKTtcbiAgICBpZiAoZXhpc3RzKHBhdGguam9pbihwb3RlbnRpYWxOU1NEQkRpciwgJ2NlcnQ4LmRiJykpKSB7XG4gICAgICBkZWJ1ZyhgRm91bmQgbGVnYWN5IE5TUyBkYXRhYmFzZSBpbiAkeyBwb3RlbnRpYWxOU1NEQkRpciB9LCBydW5uaW5nIGNhbGxiYWNrLi4uYClcbiAgICAgIGNhbGxiYWNrKHBvdGVudGlhbE5TU0RCRGlyLCAnbGVnYWN5Jyk7XG4gICAgfVxuICAgIGlmIChleGlzdHMocGF0aC5qb2luKHBvdGVudGlhbE5TU0RCRGlyLCAnY2VydDkuZGInKSkpIHtcbiAgICAgIGRlYnVnKGBGb3VuZCBtb2Rlcm4gTlNTIGRhdGFiYXNlIGluICR7IHBvdGVudGlhbE5TU0RCRGlyIH0sIHJ1bm5pbmcgY2FsbGJhY2suLi5gKVxuICAgICAgY2FsbGJhY2socG90ZW50aWFsTlNTREJEaXIsICdtb2Rlcm4nKTtcbiAgICB9XG4gIH0pO1xufVxuXG4vKipcbiAqICBHaXZlbiBhIGRpcmVjdG9yeSBvciBnbG9iIHBhdHRlcm4gb2YgZGlyZWN0b3JpZXMsIGF0dGVtcHQgdG8gaW5zdGFsbCB0aGVcbiAqICBDQSBjZXJ0aWZpY2F0ZSB0byBlYWNoIGRpcmVjdG9yeSBjb250YWluaW5nIGFuIE5TUyBkYXRhYmFzZS5cbiAqL1xuZXhwb3J0IGZ1bmN0aW9uIGFkZENlcnRpZmljYXRlVG9OU1NDZXJ0REIobnNzRGlyR2xvYjogc3RyaW5nLCBjZXJ0UGF0aDogc3RyaW5nLCBjZXJ0dXRpbFBhdGg6IHN0cmluZyk6IHZvaWQge1xuICBkZWJ1ZyhgdHJ5aW5nIHRvIGluc3RhbGwgY2VydGlmaWNhdGUgaW50byBOU1MgZGF0YWJhc2VzIGluICR7IG5zc0Rpckdsb2IgfWApO1xuICBkb0Zvck5TU0NlcnREQihuc3NEaXJHbG9iLCAoZGlyLCB2ZXJzaW9uKSA9PiB7XG4gICAgY29uc3QgZGlyQXJnID0gdmVyc2lvbiA9PT0gJ21vZGVybicgPyBgc3FsOiR7IGRpciB9YCA6IGRpcjtcbiAgICAgIHJ1bihjZXJ0dXRpbFBhdGgsIFsnLUEnLCAnLWQnLCBkaXJBcmcsICctdCcsICdDLCwnLCAnLWknLCBjZXJ0UGF0aCwgJy1uJywgJ2RldmNlcnQnXSk7XG4gIH0pO1xuICBkZWJ1ZyhgZmluaXNoZWQgc2Nhbm5pbmcgJiBpbnN0YWxsaW5nIGNlcnRpZmljYXRlIGluIE5TUyBkYXRhYmFzZXMgaW4gJHsgbnNzRGlyR2xvYiB9YCk7XG59XG5cbmV4cG9ydCBmdW5jdGlvbiByZW1vdmVDZXJ0aWZpY2F0ZUZyb21OU1NDZXJ0REIobnNzRGlyR2xvYjogc3RyaW5nLCBjZXJ0UGF0aDogc3RyaW5nLCBjZXJ0dXRpbFBhdGg6IHN0cmluZyk6IHZvaWQge1xuICBkZWJ1ZyhgdHJ5aW5nIHRvIHJlbW92ZSBjZXJ0aWZpY2F0ZXMgZnJvbSBOU1MgZGF0YWJhc2VzIGluICR7IG5zc0Rpckdsb2IgfWApO1xuICBkb0Zvck5TU0NlcnREQihuc3NEaXJHbG9iLCAoZGlyLCB2ZXJzaW9uKSA9PiB7XG4gICAgY29uc3QgZGlyQXJnID0gdmVyc2lvbiA9PT0gJ21vZGVybicgPyBgc3FsOiR7IGRpciB9YCA6IGRpcjtcbiAgICB0cnkge1xuICAgICAgcnVuKGNlcnR1dGlsUGF0aCwgWyctQScsICctZCcsIGRpckFyZywgJy10JywgJ0MsLCcsICctaScsIGNlcnRQYXRoLCAnLW4nLCAnZGV2Y2VydCddKTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBkZWJ1ZyhgZmFpbGVkIHRvIHJlbW92ZSAkeyBjZXJ0UGF0aCB9IGZyb20gJHsgZGlyIH0sIGNvbnRpbnVpbmcuICR7IGUudG9TdHJpbmcoKSB9YClcbiAgICB9XG4gIH0pO1xuICBkZWJ1ZyhgZmluaXNoZWQgc2Nhbm5pbmcgJiBpbnN0YWxsaW5nIGNlcnRpZmljYXRlIGluIE5TUyBkYXRhYmFzZXMgaW4gJHsgbnNzRGlyR2xvYiB9YCk7XG59XG5cbi8qKlxuICogIENoZWNrIHRvIHNlZSBpZiBGaXJlZm94IGlzIHN0aWxsIHJ1bm5pbmcsIGFuZCBpZiBzbywgYXNrIHRoZSB1c2VyIHRvIGNsb3NlXG4gKiAgaXQuIFBvbGwgdW50aWwgaXQncyBjbG9zZWQsIHRoZW4gcmV0dXJuLlxuICpcbiAqIFRoaXMgaXMgbmVlZGVkIGJlY2F1c2UgRmlyZWZveCBhcHBlYXJzIHRvIGxvYWQgdGhlIE5TUyBkYXRhYmFzZSBpbi1tZW1vcnkgb25cbiAqIHN0YXJ0dXAsIGFuZCBvdmVyd3JpdGUgb24gZXhpdC4gU28gd2UgaGF2ZSB0byBhc2sgdGhlIHVzZXIgdG8gcXVpdGUgRmlyZWZveFxuICogZmlyc3Qgc28gb3VyIGNoYW5nZXMgZG9uJ3QgZ2V0IG92ZXJ3cml0dGVuLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY2xvc2VGaXJlZm94KCk6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoaXNGaXJlZm94T3BlbigpKSB7XG4gICAgYXdhaXQgVUkuY2xvc2VGaXJlZm94QmVmb3JlQ29udGludWluZygpO1xuICAgIHdoaWxlKGlzRmlyZWZveE9wZW4oKSkge1xuICAgICAgYXdhaXQgc2xlZXAoNTApO1xuICAgIH1cbiAgfVxufVxuXG4vKipcbiAqIENoZWNrIGlmIEZpcmVmb3ggaXMgY3VycmVudGx5IG9wZW5cbiAqL1xuZnVuY3Rpb24gaXNGaXJlZm94T3BlbigpIHtcbiAgLy8gTk9URTogV2UgdXNlIHNvbWUgV2luZG93cy11bmZyaWVuZGx5IG1ldGhvZHMgaGVyZSAocHMpIGJlY2F1c2UgV2luZG93c1xuICAvLyBuZXZlciBuZWVkcyB0byBjaGVjayB0aGlzLCBiZWNhdXNlIGl0IGRvZXNuJ3QgdXBkYXRlIHRoZSBOU1MgREJcbiAgLy8gYXV0b21hdGljYWx5LlxuICBhc3NlcnQoaXNNYWMgfHwgaXNMaW51eCwgJ2NoZWNrRm9yT3BlbkZpcmVmb3ggd2FzIGludm9rZWQgb24gYSBwbGF0Zm9ybSBvdGhlciB0aGFuIE1hYyBvciBMaW51eCcpO1xuICByZXR1cm4gZXhlYygncHMgYXV4JykuaW5kZXhPZignZmlyZWZveCcpID4gLTE7XG59XG5cbmFzeW5jIGZ1bmN0aW9uIHNsZWVwKG1zOiBudW1iZXIpIHtcbiAgcmV0dXJuIG5ldyBQcm9taXNlKChyZXNvbHZlKSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIG1zKSk7XG59XG5cbi8qKlxuICogRmlyZWZveCBtYW5hZ2VzIGl0J3Mgb3duIHRydXN0IHN0b3JlIGZvciBTU0wgY2VydGlmaWNhdGVzLCB3aGljaCBjYW4gYmVcbiAqIG1hbmFnZWQgdmlhIHRoZSBjZXJ0dXRpbCBjb21tYW5kIChzdXBwbGllZCBieSBOU1MgdG9vbGluZyBwYWNrYWdlcykuIEluIHRoZVxuICogZXZlbnQgdGhhdCBjZXJ0dXRpbCBpcyBub3QgYWxyZWFkeSBpbnN0YWxsZWQsIGFuZCBlaXRoZXIgY2FuJ3QgYmUgaW5zdGFsbGVkXG4gKiAoV2luZG93cykgb3IgdGhlIHVzZXIgZG9lc24ndCB3YW50IHRvIGluc3RhbGwgaXQgKHNraXBDZXJ0dXRpbEluc3RhbGw6XG4gKiB0cnVlKSwgaXQgbWVhbnMgdGhhdCB3ZSBjYW4ndCBwcm9ncmFtbWF0aWNhbGx5IHRlbGwgRmlyZWZveCB0byB0cnVzdCBvdXJcbiAqIHJvb3QgQ0EgY2VydGlmaWNhdGUuXG4gKlxuICogVGhlcmUgaXMgYSByZWNvdXJzZSB0aG91Z2guIFdoZW4gYSBGaXJlZm94IHRhYiBpcyBkaXJlY3RlZCB0byBhIFVSTCB0aGF0XG4gKiByZXNwb25kcyB3aXRoIGEgY2VydGlmaWNhdGUsIGl0IHdpbGwgYXV0b21hdGljYWxseSBwcm9tcHQgdGhlIHVzZXIgaWYgdGhleVxuICogd2FudCB0byBhZGQgaXQgdG8gdGhlaXIgdHJ1c3RlZCBjZXJ0aWZpY2F0ZXMuIFNvIGlmIHdlIGNhbid0IGF1dG9tYXRpY2FsbHlcbiAqIGluc3RhbGwgdGhlIGNlcnRpZmljYXRlIHZpYSBjZXJ0dXRpbCwgd2UgaW5zdGVhZCBzdGFydCBhIHF1aWNrIHdlYiBzZXJ2ZXJcbiAqIGFuZCBob3N0IG91ciBjZXJ0aWZpY2F0ZSBmaWxlLiBUaGVuIHdlIG9wZW4gdGhlIGhvc3RlZCBjZXJ0IFVSTCBpbiBGaXJlZm94XG4gKiB0byBraWNrIG9mZiB0aGUgR1VJIGZsb3cuXG4gKlxuICogVGhpcyBtZXRob2QgZG9lcyBhbGwgdGhpcywgYWxvbmcgd2l0aCBwcm92aWRpbmcgdXNlciBwcm9tcHRzIGluIHRoZSB0ZXJtaW5hbFxuICogdG8gd2FsayB0aGVtIHRocm91Z2ggdGhpcyBwcm9jZXNzLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gb3BlbkNlcnRpZmljYXRlSW5GaXJlZm94KGZpcmVmb3hQYXRoOiBzdHJpbmcsIGNlcnRQYXRoOiBzdHJpbmcpOiBQcm9taXNlPHZvaWQ+IHtcbiAgZGVidWcoJ0FkZGluZyBkZXZlcnQgdG8gRmlyZWZveCB0cnVzdCBzdG9yZXMgbWFudWFsbHkuIExhdW5jaGluZyBhIHdlYnNlcnZlciB0byBob3N0IG91ciBjZXJ0aWZpY2F0ZSB0ZW1wb3JhcmlseSAuLi4nKTtcbiAgbGV0IHBvcnQgPSBhd2FpdCBnZXRQb3J0KCk7XG4gIGxldCBzZXJ2ZXIgPSBodHRwLmNyZWF0ZVNlcnZlcihhc3luYyAocmVxLCByZXMpID0+IHtcbiAgICBsZXQgeyBwYXRobmFtZSB9ID0gdXJsLnBhcnNlKHJlcS51cmwpO1xuICAgIGlmIChwYXRobmFtZSA9PT0gJy9jZXJ0aWZpY2F0ZScpIHtcbiAgICAgIHJlcy53cml0ZUhlYWQoMjAwLCB7ICdDb250ZW50LXR5cGUnOiAnYXBwbGljYXRpb24veC14NTA5LWNhLWNlcnQnIH0pO1xuICAgICAgcmVzLndyaXRlKHJlYWRGaWxlKGNlcnRQYXRoKSk7XG4gICAgICByZXMuZW5kKCk7XG4gICAgfSBlbHNlIHtcbiAgICAgIHJlcy53cml0ZUhlYWQoMjAwKTtcbiAgICAgIHJlcy53cml0ZShhd2FpdCBVSS5maXJlZm94V2l6YXJkUHJvbXB0UGFnZShgaHR0cDovL2xvY2FsaG9zdDokeyBwb3J0IH0vY2VydGlmaWNhdGVgKSk7XG4gICAgICByZXMuZW5kKCk7XG4gICAgfVxuICB9KS5saXN0ZW4ocG9ydCk7XG4gIGRlYnVnKCdDZXJ0aWZpY2F0ZSBzZXJ2ZXIgaXMgdXAuIFByaW50aW5nIGluc3RydWN0aW9ucyBmb3IgdXNlciBhbmQgbGF1bmNoaW5nIEZpcmVmb3ggd2l0aCBob3N0ZWQgY2VydGlmaWNhdGUgVVJMJyk7XG4gIGF3YWl0IFVJLnN0YXJ0RmlyZWZveFdpemFyZChgaHR0cDovL2xvY2FsaG9zdDokeyBwb3J0IH1gKTtcbiAgcnVuKGZpcmVmb3hQYXRoLCBbYGh0dHA6Ly9sb2NhbGhvc3Q6JHsgcG9ydCB9YF0pO1xuICBhd2FpdCBVSS53YWl0Rm9yRmlyZWZveFdpemFyZCgpO1xuICBzZXJ2ZXIuY2xvc2UoKTtcbn1cblxuZXhwb3J0IGZ1bmN0aW9uIGFzc2VydE5vdFRvdWNoaW5nRmlsZXMoZmlsZXBhdGg6IHN0cmluZywgb3BlcmF0aW9uOiBzdHJpbmcpOiB2b2lkIHtcbiAgICBpZiAoIWZpbGVwYXRoLnN0YXJ0c1dpdGgoY29uZmlnRGlyKSAmJiAhZmlsZXBhdGguc3RhcnRzV2l0aChnZXRMZWdhY3lDb25maWdEaXIoKSkpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihgRGV2Y2VydCBjYW5ub3QgJHsgb3BlcmF0aW9uIH0gJHsgZmlsZXBhdGggfTsgaXQgaXMgb3V0c2lkZSBrbm93biBkZXZjZXJ0IGNvbmZpZyBkaXJlY3RvcmllcyFgKTtcbiAgICB9XG59Il19