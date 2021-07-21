"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const path_1 = tslib_1.__importDefault(require("path"));
const fs_1 = require("fs");
const debug_1 = tslib_1.__importDefault(require("debug"));
const command_exists_1 = require("command-exists");
const shared_1 = require("./shared");
const utils_1 = require("../utils");
const user_interface_1 = tslib_1.__importDefault(require("../user-interface"));
const debug = debug_1.default('devcert:platforms:linux');
class LinuxPlatform {
    constructor() {
        this.FIREFOX_NSS_DIR = path_1.default.join(process.env.HOME, '.mozilla/firefox/*');
        this.CHROME_NSS_DIR = path_1.default.join(process.env.HOME, '.pki/nssdb');
        this.FIREFOX_BIN_PATH = '/usr/bin/firefox';
        this.CHROME_BIN_PATH = '/usr/bin/google-chrome';
        this.HOST_FILE_PATH = '/etc/hosts';
    }
    /**
     * Linux is surprisingly difficult. There seems to be multiple system-wide
     * repositories for certs, so we copy ours to each. However, Firefox does it's
     * usual separate trust store. Plus Chrome relies on the NSS tooling (like
     * Firefox), but uses the user's NSS database, unlike Firefox (which uses a
     * separate Mozilla one). And since Chrome doesn't prompt the user with a GUI
     * flow when opening certs, if we can't use certutil to install our certificate
     * into the user's NSS database, we're out of luck.
     */
    addToTrustStores(certificatePath, options = {}) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            debug('Adding devcert root CA to Linux system-wide trust stores');
            // run(`sudo cp ${ certificatePath } /etc/ssl/certs/devcert.crt`);
            utils_1.run('sudo', ['cp', certificatePath, '/usr/local/share/ca-certificates/devcert.crt']);
            // run(`sudo bash -c "cat ${ certificatePath } >> /etc/ssl/certs/ca-certificates.crt"`);
            utils_1.run('sudo', ['update-ca-certificates']);
            if (this.isFirefoxInstalled()) {
                // Firefox
                debug('Firefox install detected: adding devcert root CA to Firefox-specific trust stores ...');
                if (!command_exists_1.sync('certutil')) {
                    if (options.skipCertutilInstall) {
                        debug('NSS tooling is not already installed, and `skipCertutil` is true, so falling back to manual certificate install for Firefox');
                        shared_1.openCertificateInFirefox(this.FIREFOX_BIN_PATH, certificatePath);
                    }
                    else {
                        debug('NSS tooling is not already installed. Trying to install NSS tooling now with `apt install`');
                        utils_1.run('sudo', ['apt', 'install', 'libnss3-tools']);
                        debug('Installing certificate into Firefox trust stores using NSS tooling');
                        yield shared_1.closeFirefox();
                        yield shared_1.addCertificateToNSSCertDB(this.FIREFOX_NSS_DIR, certificatePath, 'certutil');
                    }
                }
            }
            else {
                debug('Firefox does not appear to be installed, skipping Firefox-specific steps...');
            }
            if (this.isChromeInstalled()) {
                debug('Chrome install detected: adding devcert root CA to Chrome trust store ...');
                if (!command_exists_1.sync('certutil')) {
                    user_interface_1.default.warnChromeOnLinuxWithoutCertutil();
                }
                else {
                    yield shared_1.closeFirefox();
                    yield shared_1.addCertificateToNSSCertDB(this.CHROME_NSS_DIR, certificatePath, 'certutil');
                }
            }
            else {
                debug('Chrome does not appear to be installed, skipping Chrome-specific steps...');
            }
        });
    }
    removeFromTrustStores(certificatePath) {
        try {
            utils_1.run('sudo', ['rm', '/usr/local/share/ca-certificates/devcert.crt']);
            utils_1.run('sudo', ['update-ca-certificates']);
        }
        catch (e) {
            debug(`failed to remove ${certificatePath} from /usr/local/share/ca-certificates, continuing. ${e.toString()}`);
        }
        if (command_exists_1.sync('certutil')) {
            if (this.isFirefoxInstalled()) {
                shared_1.removeCertificateFromNSSCertDB(this.FIREFOX_NSS_DIR, certificatePath, 'certutil');
            }
            if (this.isChromeInstalled()) {
                shared_1.removeCertificateFromNSSCertDB(this.CHROME_NSS_DIR, certificatePath, 'certutil');
            }
        }
    }
    addDomainToHostFileIfMissing(domain) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            const trimDomain = domain.trim().replace(/[\s;]/g, '');
            let hostsFileContents = fs_1.readFileSync(this.HOST_FILE_PATH, 'utf8');
            if (!hostsFileContents.includes(trimDomain)) {
                utils_1.sudoAppend(this.HOST_FILE_PATH, `127.0.0.1 ${trimDomain}\n`);
            }
        });
    }
    deleteProtectedFiles(filepath) {
        shared_1.assertNotTouchingFiles(filepath, 'delete');
        utils_1.run('sudo', ['rm', '-rf', filepath]);
    }
    readProtectedFile(filepath) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            shared_1.assertNotTouchingFiles(filepath, 'read');
            return (yield utils_1.run('sudo', ['cat', filepath])).toString().trim();
        });
    }
    writeProtectedFile(filepath, contents) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            shared_1.assertNotTouchingFiles(filepath, 'write');
            if (fs_1.existsSync(filepath)) {
                yield utils_1.run('sudo', ['rm', filepath]);
            }
            fs_1.writeFileSync(filepath, contents);
            yield utils_1.run('sudo', ['chown', '0', filepath]);
            yield utils_1.run('sudo', ['chmod', '600', filepath]);
        });
    }
    isFirefoxInstalled() {
        return fs_1.existsSync(this.FIREFOX_BIN_PATH);
    }
    isChromeInstalled() {
        return fs_1.existsSync(this.CHROME_BIN_PATH);
    }
}
exports.default = LinuxPlatform;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGludXguanMiLCJzb3VyY2VSb290IjoiL1VzZXJzL2p6ZXRsZW4vZ2l0cy9kZXZjZXJ0LyIsInNvdXJjZXMiOlsicGxhdGZvcm1zL2xpbnV4LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLHdEQUF3QjtBQUN4QiwyQkFBNEY7QUFDNUYsMERBQWdDO0FBQ2hDLG1EQUF1RDtBQUN2RCxxQ0FBcUo7QUFDckosb0NBQTJDO0FBRTNDLCtFQUFtQztBQUduQyxNQUFNLEtBQUssR0FBRyxlQUFXLENBQUMseUJBQXlCLENBQUMsQ0FBQztBQUVyRDtJQUFBO1FBRVUsb0JBQWUsR0FBRyxjQUFJLENBQUMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLG9CQUFvQixDQUFDLENBQUM7UUFDcEUsbUJBQWMsR0FBRyxjQUFJLENBQUMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLFlBQVksQ0FBQyxDQUFDO1FBQzNELHFCQUFnQixHQUFHLGtCQUFrQixDQUFDO1FBQ3RDLG9CQUFlLEdBQUcsd0JBQXdCLENBQUM7UUFFM0MsbUJBQWMsR0FBRyxZQUFZLENBQUM7SUF3R3hDLENBQUM7SUF0R0M7Ozs7Ozs7O09BUUc7SUFDRyxnQkFBZ0IsQ0FBQyxlQUF1QixFQUFFLFVBQW1CLEVBQUU7O1lBRW5FLEtBQUssQ0FBQywwREFBMEQsQ0FBQyxDQUFDO1lBQ2xFLGtFQUFrRTtZQUNsRSxXQUFHLENBQUMsTUFBTSxFQUFFLENBQUMsSUFBSSxFQUFFLGVBQWUsRUFBRSw4Q0FBOEMsQ0FBQyxDQUFDLENBQUM7WUFDckYsd0ZBQXdGO1lBQ3hGLFdBQUcsQ0FBQyxNQUFNLEVBQUUsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLENBQUM7WUFFeEMsSUFBSSxJQUFJLENBQUMsa0JBQWtCLEVBQUUsRUFBRTtnQkFDN0IsVUFBVTtnQkFDVixLQUFLLENBQUMsdUZBQXVGLENBQUMsQ0FBQztnQkFDL0YsSUFBSSxDQUFDLHFCQUFhLENBQUMs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QVEsRUFBRSxNQUFNLENBQUMsQ0FBQztZQUN6QyxPQUFPLENBQUMsTUFBTSxXQUFHLENBQUMsTUFBTSxFQUFFLENBQUMsS0FBSyxFQUFFLFFBQVEsQ0FBQyxDQUFDLENBQUMsQ0FBQyxRQUFRLEVBQUUsQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUNsRSxDQUFDO0tBQUE7SUFFSyxrQkFBa0IsQ0FBQyxRQUFnQixFQUFFLFFBQWdCOztZQUN6RCwrQkFBc0IsQ0FBQyxRQUFRLEVBQUUsT0FBTyxDQUFDLENBQUM7WUFDMUMsSUFBSSxlQUFNLENBQUMsUUFBUSxDQUFDLEVBQUU7Z0JBQ3BCLE1BQU0sV0FBRyxDQUFDLE1BQU0sRUFBRSxDQUFDLElBQUksRUFBRSxRQUFRLENBQUMsQ0FBQyxDQUFDO2FBQ3JDO1lBQ0Qsa0JBQVMsQ0FBQyxRQUFRLEVBQUUsUUFBUSxDQUFDLENBQUM7WUFDOUIsTUFBTSxXQUFHLENBQUMsTUFBTSxFQUFFLENBQUMsT0FBTyxFQUFFLEdBQUcsRUFBRSxRQUFRLENBQUMsQ0FBQyxDQUFDO1lBQzVDLE1BQU0sV0FBRyxDQUFDLE1BQU0sRUFBRSxDQUFDLE9BQU8sRUFBRSxLQUFLLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQztRQUNoRCxDQUFDO0tBQUE7SUFFTyxrQkFBa0I7UUFDeEIsT0FBTyxlQUFNLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7SUFDdkMsQ0FBQztJQUVPLGlCQUFpQjtRQUN2QixPQUFPLGVBQU0sQ0FBQyxJQUFJLENBQUMsZUFBZSxDQUFDLENBQUM7SUFDdEMsQ0FBQztDQUVGO0FBL0dELGdDQStHQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBwYXRoIGZyb20gJ3BhdGgnO1xuaW1wb3J0IHsgZXhpc3RzU3luYyBhcyBleGlzdHMsIHJlYWRGaWxlU3luYyBhcyByZWFkLCB3cml0ZUZpbGVTeW5jIGFzIHdyaXRlRmlsZSB9IGZyb20gJ2ZzJztcbmltcG9ydCBjcmVhdGVEZWJ1ZyBmcm9tICdkZWJ1Zyc7XG5pbXBvcnQgeyBzeW5jIGFzIGNvbW1hbmRFeGlzdHMgfSBmcm9tICdjb21tYW5kLWV4aXN0cyc7XG5pbXBvcnQgeyBhZGRDZXJ0aWZpY2F0ZVRvTlNTQ2VydERCLCBhc3NlcnROb3RUb3VjaGluZ0ZpbGVzLCBvcGVuQ2VydGlmaWNhdGVJbkZpcmVmb3gsIGNsb3NlRmlyZWZveCwgcmVtb3ZlQ2VydGlmaWNhdGVGcm9tTlNTQ2VydERCIH0gZnJvbSAnLi9zaGFyZWQnO1xuaW1wb3J0IHsgcnVuLCBzdWRvQXBwZW5kIH0gZnJvbSAnLi4vdXRpbHMnO1xuaW1wb3J0IHsgT3B0aW9ucyB9IGZyb20gJy4uL2luZGV4JztcbmltcG9ydCBVSSBmcm9tICcuLi91c2VyLWludGVyZmFjZSc7XG5pbXBvcnQgeyBQbGF0Zm9ybSB9IGZyb20gJy4nO1xuXG5jb25zdCBkZWJ1ZyA9IGNyZWF0ZURlYnVnKCdkZXZjZXJ0OnBsYXRmb3JtczpsaW51eCcpO1xuXG5leHBvcnQgZGVmYXVsdCBjbGFzcyBMaW51eFBsYXRmb3JtIGltcGxlbWVudHMgUGxhdGZvcm0ge1xuXG4gIHByaXZhdGUgRklSRUZPWF9OU1NfRElSID0gcGF0aC5qb2luKHByb2Nlc3MuZW52LkhPTUUsICcubW96aWxsYS9maXJlZm94LyonKTtcbiAgcHJpdmF0ZSBDSFJPTUVfTlNTX0RJUiA9IHBhdGguam9pbihwcm9jZXNzLmVudi5IT01FLCAnLnBraS9uc3NkYicpO1xuICBwcml2YXRlIEZJUkVGT1hfQklOX1BBVEggPSAnL3Vzci9iaW4vZmlyZWZveCc7XG4gIHByaXZhdGUgQ0hST01FX0JJTl9QQVRIID0gJy91c3IvYmluL2dvb2dsZS1jaHJvbWUnO1xuXG4gIHByaXZhdGUgSE9TVF9GSUxFX1BBVEggPSAnL2V0Yy9ob3N0cyc7XG5cbiAgLyoqXG4gICAqIExpbnV4IGlzIHN1cnByaXNpbmdseSBkaWZmaWN1bHQuIFRoZXJlIHNlZW1zIHRvIGJlIG11bHRpcGxlIHN5c3RlbS13aWRlXG4gICAqIHJlcG9zaXRvcmllcyBmb3IgY2VydHMsIHNvIHdlIGNvcHkgb3VycyB0byBlYWNoLiBIb3dldmVyLCBGaXJlZm94IGRvZXMgaXQnc1xuICAgKiB1c3VhbCBzZXBhcmF0ZSB0cnVzdCBzdG9yZS4gUGx1cyBDaHJvbWUgcmVsaWVzIG9uIHRoZSBOU1MgdG9vbGluZyAobGlrZVxuICAgKiBGaXJlZm94KSwgYnV0IHVzZXMgdGhlIHVzZXIncyBOU1MgZGF0YWJhc2UsIHVubGlrZSBGaXJlZm94ICh3aGljaCB1c2VzIGFcbiAgICogc2VwYXJhdGUgTW96aWxsYSBvbmUpLiBBbmQgc2luY2UgQ2hyb21lIGRvZXNuJ3QgcHJvbXB0IHRoZSB1c2VyIHdpdGggYSBHVUlcbiAgICogZmxvdyB3aGVuIG9wZW5pbmcgY2VydHMsIGlmIHdlIGNhbid0IHVzZSBjZXJ0dXRpbCB0byBpbnN0YWxsIG91ciBjZXJ0aWZpY2F0ZVxuICAgKiBpbnRvIHRoZSB1c2VyJ3MgTlNTIGRhdGFiYXNlLCB3ZSdyZSBvdXQgb2YgbHVjay5cbiAgICovXG4gIGFzeW5jIGFkZFRvVHJ1c3RTdG9yZXMoY2VydGlmaWNhdGVQYXRoOiBzdHJpbmcsIG9wdGlvbnM6IE9wdGlvbnMgPSB7fSk6IFByb21pc2U8dm9pZD4ge1xuXG4gICAgZGVidWcoJ0FkZGluZyBkZXZjZXJ0IHJvb3QgQ0EgdG8gTGludXggc3lzdGVtLXdpZGUgdHJ1c3Qgc3RvcmVzJyk7XG4gICAgLy8gcnVuKGBzdWRvIGNwICR7IGNlcnRpZmljYXRlUGF0aCB9IC9ldGMvc3NsL2NlcnRzL2RldmNlcnQuY3J0YCk7XG4gICAgcnVuKCdzdWRvJywgWydjcCcsIGNlcnRpZmljYXRlUGF0aCwgJy91c3IvbG9jYWwvc2hhcmUvY2EtY2VydGlmaWNhdGVzL2RldmNlcnQuY3J0J10pO1xuICAgIC8vIHJ1bihgc3VkbyBiYXNoIC1jIFwiY2F0ICR7IGNlcnRpZmljYXRlUGF0aCB9ID4+IC9ldGMvc3NsL2NlcnRzL2NhLWNlcnRpZmljYXRlcy5jcnRcImApO1xuICAgIHJ1bignc3VkbycsIFsndXBkYXRlLWNhLWNlcnRpZmljYXRlcyddKTtcblxuICAgIGlmICh0aGlzLmlzRmlyZWZveEluc3RhbGxlZCgpKSB7XG4gICAgICAvLyBGaXJlZm94XG4gICAgICBkZWJ1ZygnRmlyZWZveCBpbnN0YWxsIGRldGVjdGVkOiBhZGRpbmcgZGV2Y2VydCByb290IENBIHRvIEZpcmVmb3gtc3BlY2lmaWMgdHJ1c3Qgc3RvcmVzIC4uLicpO1xuICAgICAgaWYgKCFjb21tYW5kRXhpc3RzKCdjZXJ0dXRpbCcpKSB7XG4gICAgICAgIGlmIChvcHRpb25zLnNraXBDZXJ0dXRpbEluc3RhbGwpIHtcbiAgICAgICAgICBkZWJ1ZygnTlNTIHRvb2xpbmcgaXMgbm90IGFscmVhZHkgaW5zdGFsbGVkLCBhbmQgYHNraXBDZXJ0dXRpbGAgaXMgdHJ1ZSwgc28gZmFsbGluZyBiYWNrIHRvIG1hbnVhbCBjZXJ0aWZpY2F0ZSBpbnN0YWxsIGZvciBGaXJlZm94Jyk7XG4gICAgICAgICAgb3BlbkNlcnRpZmljYXRlSW5GaXJlZm94KHRoaXMuRklSRUZPWF9CSU5fUEFUSCwgY2VydGlmaWNhdGVQYXRoKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBkZWJ1ZygnTlNTIHRvb2xpbmcgaXMgbm90IGFscmVhZHkgaW5zdGFsbGVkLiBUcnlpbmcgdG8gaW5zdGFsbCBOU1MgdG9vbGluZyBub3cgd2l0aCBgYXB0IGluc3RhbGxgJyk7XG4gICAgICAgICAgcnVuKCdzdWRvJywgIFsnYXB0JywgJ2luc3RhbGwnLCAnbGlibnNzMy10b29scyddKTtcbiAgICAgICAgICBkZWJ1ZygnSW5zdGFsbGluZyBjZXJ0aWZpY2F0ZSBpbnRvIEZpcmVmb3ggdHJ1c3Qgc3RvcmVzIHVzaW5nIE5TUyB0b29saW5nJyk7XG4gICAgICAgICAgYXdhaXQgY2xvc2VGaXJlZm94KCk7XG4gICAgICAgICAgYXdhaXQgYWRkQ2VydGlmaWNhdGVUb05TU0NlcnREQih0aGlzLkZJUkVGT1hfTlNTX0RJUiwgY2VydGlmaWNhdGVQYXRoLCAnY2VydHV0aWwnKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBkZWJ1ZygnRmlyZWZveCBkb2VzIG5vdCBhcHBlYXIgdG8gYmUgaW5zdGFsbGVkLCBza2lwcGluZyBGaXJlZm94LXNwZWNpZmljIHN0ZXBzLi4uJyk7XG4gICAgfVxuXG4gICAgaWYgKHRoaXMuaXNDaHJvbWVJbnN0YWxsZWQoKSkge1xuICAgICAgZGVidWcoJ0Nocm9tZSBpbnN0YWxsIGRldGVjdGVkOiBhZGRpbmcgZGV2Y2VydCByb290IENBIHRvIENocm9tZSB0cnVzdCBzdG9yZSAuLi4nKTtcbiAgICAgIGlmICghY29tbWFuZEV4aXN0cygnY2VydHV0aWwnKSkge1xuICAgICAgICBVSS53YXJuQ2hyb21lT25MaW51eFdpdGhvdXRDZXJ0dXRpbCgpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgYXdhaXQgY2xvc2VGaXJlZm94KCk7XG4gICAgICAgIGF3YWl0IGFkZENlcnRpZmljYXRlVG9OU1NDZXJ0REIodGhpcy5DSFJPTUVfTlNTX0RJUiwgY2VydGlmaWNhdGVQYXRoLCAnY2VydHV0aWwnKTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgZGVidWcoJ0Nocm9tZSBkb2VzIG5vdCBhcHBlYXIgdG8gYmUgaW5zdGFsbGVkLCBza2lwcGluZyBDaHJvbWUtc3BlY2lmaWMgc3RlcHMuLi4nKTtcbiAgICB9XG4gIH1cbiAgXG4gIHJlbW92ZUZyb21UcnVzdFN0b3JlcyhjZXJ0aWZpY2F0ZVBhdGg6IHN0cmluZykge1xuICAgIHRyeSB7XG4gICAgICBydW4oJ3N1ZG8nLCBbJ3JtJywgJy91c3IvbG9jYWwvc2hhcmUvY2EtY2VydGlmaWNhdGVzL2RldmNlcnQuY3J0J10pO1xuICAgICAgcnVuKCdzdWRvJywgWyd1cGRhdGUtY2EtY2VydGlmaWNhdGVzJ10pO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgIGRlYnVnKGBmYWlsZWQgdG8gcmVtb3ZlICR7IGNlcnRpZmljYXRlUGF0aCB9IGZyb20gL3Vzci9sb2NhbC9zaGFyZS9jYS1jZXJ0aWZpY2F0ZXMsIGNvbnRpbnVpbmcuICR7IGUudG9TdHJpbmcoKSB9YCk7XG4gICAgfVxuICAgIGlmIChjb21tYW5kRXhpc3RzKCdjZXJ0dXRpbCcpKSB7XG4gICAgICBpZiAodGhpcy5pc0ZpcmVmb3hJbnN0YWxsZWQoKSkge1xuICAgICAgICByZW1vdmVDZXJ0aWZpY2F0ZUZyb21OU1NDZXJ0REIodGhpcy5GSVJFRk9YX05TU19ESVIsIGNlcnRpZmljYXRlUGF0aCwgJ2NlcnR1dGlsJyk7XG4gICAgICB9XG4gICAgICBpZiAodGhpcy5pc0Nocm9tZUluc3RhbGxlZCgpKSB7XG4gICAgICAgIHJlbW92ZUNlcnRpZmljYXRlRnJvbU5TU0NlcnREQih0aGlzLkNIUk9NRV9OU1NfRElSLCBjZXJ0aWZpY2F0ZVBhdGgsICdjZXJ0dXRpbCcpO1xuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIGFzeW5jIGFkZERvbWFpblRvSG9zdEZpbGVJZk1pc3NpbmcoZG9tYWluOiBzdHJpbmcpIHtcbiAgICBjb25zdCB0cmltRG9tYWluID0gZG9tYWluLnRyaW0oKS5yZXBsYWNlKC9bXFxzO10vZywnJylcbiAgICBsZXQgaG9zdHNGaWxlQ29udGVudHMgPSByZWFkKHRoaXMuSE9TVF9GSUxFX1BBVEgsICd1dGY4Jyk7XG4gICAgaWYgKCFob3N0c0ZpbGVDb250ZW50cy5pbmNsdWRlcyh0cmltRG9tYWluKSkge1xuICAgICAgc3Vkb0FwcGVuZCh0aGlzLkhPU1RfRklMRV9QQVRILCBgMTI3LjAuMC4xICR7dHJpbURvbWFpbn1cXG5gKTtcbiAgICB9XG4gIH1cblxuICBkZWxldGVQcm90ZWN0ZWRGaWxlcyhmaWxlcGF0aDogc3RyaW5nKSB7XG4gICAgYXNzZXJ0Tm90VG91Y2hpbmdGaWxlcyhmaWxlcGF0aCwgJ2RlbGV0ZScpO1xuICAgIHJ1bignc3VkbycsIFsncm0nLCAnLXJmJywgZmlsZXBhdGhdKTtcbiAgfVxuXG4gIGFzeW5jIHJlYWRQcm90ZWN0ZWRGaWxlKGZpbGVwYXRoOiBzdHJpbmcpIHtcbiAgICBhc3NlcnROb3RUb3VjaGluZ0ZpbGVzKGZpbGVwYXRoLCAncmVhZCcpO1xuICAgIHJldHVybiAoYXdhaXQgcnVuKCdzdWRvJywgWydjYXQnLCBmaWxlcGF0aF0pKS50b1N0cmluZygpLnRyaW0oKTtcbiAgfVxuXG4gIGFzeW5jIHdyaXRlUHJvdGVjdGVkRmlsZShmaWxlcGF0aDogc3RyaW5nLCBjb250ZW50czogc3RyaW5nKSB7XG4gICAgYXNzZXJ0Tm90VG91Y2hpbmdGaWxlcyhmaWxlcGF0aCwgJ3dyaXRlJyk7XG4gICAgaWYgKGV4aXN0cyhmaWxlcGF0aCkpIHtcbiAgICAgIGF3YWl0IHJ1bignc3VkbycsIFsncm0nLCBmaWxlcGF0aF0pO1xuICAgIH1cbiAgICB3cml0ZUZpbGUoZmlsZXBhdGgsIGNvbnRlbnRzKTtcbiAgICBhd2FpdCBydW4oJ3N1ZG8nLCBbJ2Nob3duJywgJzAnLCBmaWxlcGF0aF0pO1xuICAgIGF3YWl0IHJ1bignc3VkbycsIFsnY2htb2QnLCAnNjAwJywgZmlsZXBhdGhdKTtcbiAgfVxuXG4gIHByaXZhdGUgaXNGaXJlZm94SW5zdGFsbGVkKCkge1xuICAgIHJldHVybiBleGlzdHModGhpcy5GSVJFRk9YX0JJTl9QQVRIKTtcbiAgfVxuXG4gIHByaXZhdGUgaXNDaHJvbWVJbnN0YWxsZWQoKSB7XG4gICAgcmV0dXJuIGV4aXN0cyh0aGlzLkNIUk9NRV9CSU5fUEFUSCk7XG4gIH1cblxufSJdfQ==