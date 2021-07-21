"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const debug_1 = tslib_1.__importDefault(require("debug"));
const crypto_1 = tslib_1.__importDefault(require("crypto"));
const fs_1 = require("fs");
const rimraf_1 = require("rimraf");
const shared_1 = require("./shared");
const utils_1 = require("../utils");
const user_interface_1 = tslib_1.__importDefault(require("../user-interface"));
const debug = debug_1.default('devcert:platforms:windows');
let encryptionKey;
class WindowsPlatform {
    constructor() {
        this.HOST_FILE_PATH = 'C:\\Windows\\System32\\Drivers\\etc\\hosts';
    }
    /**
     * Windows is at least simple. Like macOS, most applications will delegate to
     * the system trust store, which is updated with the confusingly named
     * `certutil` exe (not the same as the NSS/Mozilla certutil). Firefox does it's
     * own thing as usual, and getting a copy of NSS certutil onto the Windows
     * machine to try updating the Firefox store is basically a nightmare, so we
     * don't even try it - we just bail out to the GUI.
     */
    addToTrustStores(certificatePath, options = {}) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            // IE, Chrome, system utils
            debug('adding devcert root to Windows OS trust store');
            try {
                utils_1.run('certutil', ['-addstore', '-user', 'root', certificatePath]);
            }
            catch (e) {
                e.output.map((buffer) => {
                    if (buffer) {
                        console.log(buffer.toString());
                    }
                });
            }
            debug('adding devcert root to Firefox trust store');
            // Firefox (don't even try NSS certutil, no easy install for Windows)
            try {
                yield shared_1.openCertificateInFirefox('start firefox', certificatePath);
            }
            catch (_a) {
                debug('Error opening Firefox, most likely Firefox is not installed');
            }
        });
    }
    removeFromTrustStores(certificatePath) {
        debug('removing devcert root from Windows OS trust store');
        try {
            console.warn('Removing old certificates from trust stores. You may be prompted to grant permission for this. It\'s safe to delete old devcert certificates.');
            utils_1.run('certutil', ['-delstore', '-user', 'root', 'devcert']);
        }
        catch (e) {
            debug(`failed to remove ${certificatePath} from Windows OS trust store, continuing. ${e.toString()}`);
        }
    }
    addDomainToHostFileIfMissing(domain) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            let hostsFileContents = fs_1.readFileSync(this.HOST_FILE_PATH, 'utf8');
            if (!hostsFileContents.includes(domain)) {
                yield utils_1.sudo(`echo 127.0.0.1  ${domain} >> ${this.HOST_FILE_PATH}`);
            }
        });
    }
    deleteProtectedFiles(filepath) {
        shared_1.assertNotTouchingFiles(filepath, 'delete');
        rimraf_1.sync(filepath);
    }
    readProtectedFile(filepath) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            shared_1.assertNotTouchingFiles(filepath, 'read');
            if (!encryptionKey) {
                encryptionKey = yield user_interface_1.default.getWindowsEncryptionPassword();
            }
            // Try to decrypt the file
            try {
                return this.decrypt(fs_1.readFileSync(filepath, 'utf8'), encryptionKey);
            }
            catch (e) {
                // If it's a bad password, clear the cached copy and retry
                if (e.message.indexOf('bad decrypt') >= -1) {
                    encryptionKey = null;
                    return yield this.readProtectedFile(filepath);
                }
                throw e;
            }
        });
    }
    writeProtectedFile(filepath, contents) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            shared_1.assertNotTouchingFiles(filepath, 'write');
            if (!encryptionKey) {
                encryptionKey = yield user_interface_1.default.getWindowsEncryptionPassword();
            }
            let encryptedContents = this.encrypt(contents, encryptionKey);
            fs_1.writeFileSync(filepath, encryptedContents);
        });
    }
    encrypt(text, key) {
        let cipher = crypto_1.default.createCipher('aes256', new Buffer(key));
        return cipher.update(text, 'utf8', 'hex') + cipher.final('hex');
    }
    decrypt(encrypted, key) {
        let decipher = crypto_1.default.createDecipher('aes256', new Buffer(key));
        return decipher.update(encrypted, 'hex', 'utf8') + decipher.final('utf8');
    }
}
exports.default = WindowsPlatform;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoid2luMzIuanMiLCJzb3VyY2VSb290IjoiL1VzZXJzL2p6ZXRsZW4vZ2l0cy9kZXZjZXJ0LyIsInNvdXJjZXMiOlsicGxhdGZvcm1zL3dpbjMyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLDBEQUFnQztBQUNoQyw0REFBNEI7QUFDNUIsMkJBQWtFO0FBQ2xFLG1DQUF3QztBQUV4QyxxQ0FBNEU7QUFFNUUsb0NBQXFDO0FBQ3JDLCtFQUFtQztBQUVuQyxNQUFNLEtBQUssR0FBRyxlQUFXLENBQUMsMkJBQTJCLENBQUMsQ0FBQztBQUV2RCxJQUFJLGFBQXFCLENBQUM7QUFFMUI7SUFBQTtRQUVVLG1CQUFjLEdBQUcsNENBQTRDLENBQUM7SUEwRnhFLENBQUM7SUF4RkM7Ozs7Ozs7T0FPRztJQUNHLGdCQUFnQixDQUFDLGVBQXVCLEVBQUUsVUFBbUIsRUFBRTs7WUFDbkUsMkJBQTJCO1lBQzNCLEtBQUssQ0FBQywrQ0FBK0MsQ0FBQyxDQUFBO1lBQ3RELElBQUk7Z0JBQ0YsV0FBRyxDQUFDLFVBQVUsRUFBRSxDQUFDLFdBQVcsRUFBRSxPQUFPLEVBQUUsTUFBTSxFQUFFLGVBQWUsQ0FBQyxDQUFDLENBQUM7YUFDbEU7WUFBQyxPQUFPLENBQUMsRUFBRTtnQkFDVixDQUFDLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLE1BQWMsRUFBRSxFQUFFO29CQUM5QixJQUFJLE1BQU0sRUFBRTt3QkFDVixPQUFPLENBQUMsR0FBRyxDQUFDLE1BQU0sQ0FBQyxRQUFRLEVBQUUsQ0FBQyxDQUFDO3FCQUNoQztnQkFDSCxDQUFDLENBQUMsQ0FBQzthQUNKO1lBQ0QsS0FBSyxDQUFDLDRDQUE0QyxDQUFDLENBQUE7WUFDbkQscUVBQXFFO1lBQ3JFLElBQUk7Z0JBQ0YsTUFBTSxpQ0FBd0IsQ0FBQyxlQUFlLEVBQUUsZUFBZSxDQUFDLENBQUM7YUFDbEU7WUFBQyxXQUFNO2dCQUNOLEtBQUssQ0FBQyw2REFBNkQsQ0FBQyxDQUFDO2FBQ3RFO1FBQ0gsQ0FB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LE1BQU0sQ0FBQyxTQUFTLEVBQUUsS0FBSyxFQUFFLE1BQU0sQ0FBQyxHQUFHLFFBQVEsQ0FBQyxLQUFLLENBQUMsTUFBTSxDQUFDLENBQUM7SUFDNUUsQ0FBQztDQUVGO0FBNUZELGtDQTRGQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBjcmVhdGVEZWJ1ZyBmcm9tICdkZWJ1Zyc7XG5pbXBvcnQgY3J5cHRvIGZyb20gJ2NyeXB0byc7XG5pbXBvcnQgeyB3cml0ZUZpbGVTeW5jIGFzIHdyaXRlLCByZWFkRmlsZVN5bmMgYXMgcmVhZCB9IGZyb20gJ2ZzJztcbmltcG9ydCB7IHN5bmMgYXMgcmltcmFmIH0gZnJvbSAncmltcmFmJztcbmltcG9ydCB7IE9wdGlvbnMgfSBmcm9tICcuLi9pbmRleCc7XG5pbXBvcnQgeyBhc3NlcnROb3RUb3VjaGluZ0ZpbGVzLCBvcGVuQ2VydGlmaWNhdGVJbkZpcmVmb3ggfSBmcm9tICcuL3NoYXJlZCc7XG5pbXBvcnQgeyBQbGF0Zm9ybSB9IGZyb20gJy4nO1xuaW1wb3J0IHsgcnVuLCBzdWRvIH0gZnJvbSAnLi4vdXRpbHMnO1xuaW1wb3J0IFVJIGZyb20gJy4uL3VzZXItaW50ZXJmYWNlJztcblxuY29uc3QgZGVidWcgPSBjcmVhdGVEZWJ1ZygnZGV2Y2VydDpwbGF0Zm9ybXM6d2luZG93cycpO1xuXG5sZXQgZW5jcnlwdGlvbktleTogc3RyaW5nO1xuXG5leHBvcnQgZGVmYXVsdCBjbGFzcyBXaW5kb3dzUGxhdGZvcm0gaW1wbGVtZW50cyBQbGF0Zm9ybSB7XG5cbiAgcHJpdmF0ZSBIT1NUX0ZJTEVfUEFUSCA9ICdDOlxcXFxXaW5kb3dzXFxcXFN5c3RlbTMyXFxcXERyaXZlcnNcXFxcZXRjXFxcXGhvc3RzJztcblxuICAvKipcbiAgICogV2luZG93cyBpcyBhdCBsZWFzdCBzaW1wbGUuIExpa2UgbWFjT1MsIG1vc3QgYXBwbGljYXRpb25zIHdpbGwgZGVsZWdhdGUgdG9cbiAgICogdGhlIHN5c3RlbSB0cnVzdCBzdG9yZSwgd2hpY2ggaXMgdXBkYXRlZCB3aXRoIHRoZSBjb25mdXNpbmdseSBuYW1lZFxuICAgKiBgY2VydHV0aWxgIGV4ZSAobm90IHRoZSBzYW1lIGFzIHRoZSBOU1MvTW96aWxsYSBjZXJ0dXRpbCkuIEZpcmVmb3ggZG9lcyBpdCdzXG4gICAqIG93biB0aGluZyBhcyB1c3VhbCwgYW5kIGdldHRpbmcgYSBjb3B5IG9mIE5TUyBjZXJ0dXRpbCBvbnRvIHRoZSBXaW5kb3dzXG4gICAqIG1hY2hpbmUgdG8gdHJ5IHVwZGF0aW5nIHRoZSBGaXJlZm94IHN0b3JlIGlzIGJhc2ljYWxseSBhIG5pZ2h0bWFyZSwgc28gd2VcbiAgICogZG9uJ3QgZXZlbiB0cnkgaXQgLSB3ZSBqdXN0IGJhaWwgb3V0IHRvIHRoZSBHVUkuXG4gICAqL1xuICBhc3luYyBhZGRUb1RydXN0U3RvcmVzKGNlcnRpZmljYXRlUGF0aDogc3RyaW5nLCBvcHRpb25zOiBPcHRpb25zID0ge30pOiBQcm9taXNlPHZvaWQ+IHtcbiAgICAvLyBJRSwgQ2hyb21lLCBzeXN0ZW0gdXRpbHNcbiAgICBkZWJ1ZygnYWRkaW5nIGRldmNlcnQgcm9vdCB0byBXaW5kb3dzIE9TIHRydXN0IHN0b3JlJylcbiAgICB0cnkge1xuICAgICAgcnVuKCdjZXJ0dXRpbCcsIFsnLWFkZHN0b3JlJywgJy11c2VyJywgJ3Jvb3QnLCBjZXJ0aWZpY2F0ZVBhdGhdKTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBlLm91dHB1dC5tYXAoKGJ1ZmZlcjogQnVmZmVyKSA9PiB7XG4gICAgICAgIGlmIChidWZmZXIpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhidWZmZXIudG9TdHJpbmcoKSk7XG4gICAgICAgIH1cbiAgICAgIH0pO1xuICAgIH1cbiAgICBkZWJ1ZygnYWRkaW5nIGRldmNlcnQgcm9vdCB0byBGaXJlZm94IHRydXN0IHN0b3JlJylcbiAgICAvLyBGaXJlZm94IChkb24ndCBldmVuIHRyeSBOU1MgY2VydHV0aWwsIG5vIGVhc3kgaW5zdGFsbCBmb3IgV2luZG93cylcbiAgICB0cnkge1xuICAgICAgYXdhaXQgb3BlbkNlcnRpZmljYXRlSW5GaXJlZm94KCdzdGFydCBmaXJlZm94JywgY2VydGlmaWNhdGVQYXRoKTtcbiAgICB9IGNhdGNoIHtcbiAgICAgIGRlYnVnKCdFcnJvciBvcGVuaW5nIEZpcmVmb3gsIG1vc3QgbGlrZWx5IEZpcmVmb3ggaXMgbm90IGluc3RhbGxlZCcpO1xuICAgIH1cbiAgfVxuICBcbiAgcmVtb3ZlRnJvbVRydXN0U3RvcmVzKGNlcnRpZmljYXRlUGF0aDogc3RyaW5nKSB7XG4gICAgZGVidWcoJ3JlbW92aW5nIGRldmNlcnQgcm9vdCBmcm9tIFdpbmRvd3MgT1MgdHJ1c3Qgc3RvcmUnKTtcbiAgICB0cnkge1xuICAgICAgY29uc29sZS53YXJuKCdSZW1vdmluZyBvbGQgY2VydGlmaWNhdGVzIGZyb20gdHJ1c3Qgc3RvcmVzLiBZb3UgbWF5IGJlIHByb21wdGVkIHRvIGdyYW50IHBlcm1pc3Npb24gZm9yIHRoaXMuIEl0XFwncyBzYWZlIHRvIGRlbGV0ZSBvbGQgZGV2Y2VydCBjZXJ0aWZpY2F0ZXMuJyk7XG4gICAgICBydW4oJ2NlcnR1dGlsJywgWyctZGVsc3RvcmUnLCAnLXVzZXInLCAncm9vdCcsICdkZXZjZXJ0J10pO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgIGRlYnVnKGBmYWlsZWQgdG8gcmVtb3ZlICR7IGNlcnRpZmljYXRlUGF0aCB9IGZyb20gV2luZG93cyBPUyB0cnVzdCBzdG9yZSwgY29udGludWluZy4gJHsgZS50b1N0cmluZygpIH1gKVxuICAgIH1cbiAgfVxuXG4gIGFzeW5jIGFkZERvbWFpblRvSG9zdEZpbGVJZk1pc3NpbmcoZG9tYWluOiBzdHJpbmcpIHtcbiAgICBsZXQgaG9zdHNGaWxlQ29udGVudHMgPSByZWFkKHRoaXMuSE9TVF9GSUxFX1BBVEgsICd1dGY4Jyk7XG4gICAgaWYgKCFob3N0c0ZpbGVDb250ZW50cy5pbmNsdWRlcyhkb21haW4pKSB7XG4gICAgICBhd2FpdCBzdWRvKGBlY2hvIDEyNy4wLjAuMSAgJHsgZG9tYWluIH0gPj4gJHsgdGhpcy5IT1NUX0ZJTEVfUEFUSCB9YCk7XG4gICAgfVxuICB9XG4gIFxuICBkZWxldGVQcm90ZWN0ZWRGaWxlcyhmaWxlcGF0aDogc3RyaW5nKSB7XG4gICAgYXNzZXJ0Tm90VG91Y2hpbmdGaWxlcyhmaWxlcGF0aCwgJ2RlbGV0ZScpO1xuICAgIHJpbXJhZihmaWxlcGF0aCk7XG4gIH1cblxuICBhc3luYyByZWFkUHJvdGVjdGVkRmlsZShmaWxlcGF0aDogc3RyaW5nKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgICBhc3NlcnROb3RUb3VjaGluZ0ZpbGVzKGZpbGVwYXRoLCAncmVhZCcpO1xuICAgIGlmICghZW5jcnlwdGlvbktleSkge1xuICAgICAgZW5jcnlwdGlvbktleSA9IGF3YWl0IFVJLmdldFdpbmRvd3NFbmNyeXB0aW9uUGFzc3dvcmQoKTtcbiAgICB9XG4gICAgLy8gVHJ5IHRvIGRlY3J5cHQgdGhlIGZpbGVcbiAgICB0cnkge1xuICAgICAgcmV0dXJuIHRoaXMuZGVjcnlwdChyZWFkKGZpbGVwYXRoLCAndXRmOCcpLCBlbmNyeXB0aW9uS2V5KTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAvLyBJZiBpdCdzIGEgYmFkIHBhc3N3b3JkLCBjbGVhciB0aGUgY2FjaGVkIGNvcHkgYW5kIHJldHJ5XG4gICAgICBpZiAoZS5tZXNzYWdlLmluZGV4T2YoJ2JhZCBkZWNyeXB0JykgPj0gLTEpIHtcbiAgICAgICAgZW5jcnlwdGlvbktleSA9IG51bGw7XG4gICAgICAgIHJldHVybiBhd2FpdCB0aGlzLnJlYWRQcm90ZWN0ZWRGaWxlKGZpbGVwYXRoKTtcbiAgICAgIH1cbiAgICAgIHRocm93IGU7XG4gICAgfVxuICB9XG5cbiAgYXN5bmMgd3JpdGVQcm90ZWN0ZWRGaWxlKGZpbGVwYXRoOiBzdHJpbmcsIGNvbnRlbnRzOiBzdHJpbmcpIHtcbiAgICBhc3NlcnROb3RUb3VjaGluZ0ZpbGVzKGZpbGVwYXRoLCAnd3JpdGUnKTtcbiAgICBpZiAoIWVuY3J5cHRpb25LZXkpIHtcbiAgICAgIGVuY3J5cHRpb25LZXkgPSBhd2FpdCBVSS5nZXRXaW5kb3dzRW5jcnlwdGlvblBhc3N3b3JkKCk7XG4gICAgfVxuICAgIGxldCBlbmNyeXB0ZWRDb250ZW50cyA9IHRoaXMuZW5jcnlwdChjb250ZW50cywgZW5jcnlwdGlvbktleSk7XG4gICAgd3JpdGUoZmlsZXBhdGgsIGVuY3J5cHRlZENvbnRlbnRzKTtcbiAgfVxuXG4gIHByaXZhdGUgZW5jcnlwdCh0ZXh0OiBzdHJpbmcsIGtleTogc3RyaW5nKSB7XG4gICAgbGV0IGNpcGhlciA9IGNyeXB0by5jcmVhdGVDaXBoZXIoJ2FlczI1NicsIG5ldyBCdWZmZXIoa2V5KSk7XG4gICAgcmV0dXJuIGNpcGhlci51cGRhdGUodGV4dCwgJ3V0ZjgnLCAnaGV4JykgKyBjaXBoZXIuZmluYWwoJ2hleCcpO1xuICB9XG5cbiAgcHJpdmF0ZSBkZWNyeXB0KGVuY3J5cHRlZDogc3RyaW5nLCBrZXk6IHN0cmluZykge1xuICAgIGxldCBkZWNpcGhlciA9IGNyeXB0by5jcmVhdGVEZWNpcGhlcignYWVzMjU2JywgbmV3IEJ1ZmZlcihrZXkpKTtcbiAgICByZXR1cm4gZGVjaXBoZXIudXBkYXRlKGVuY3J5cHRlZCwgJ2hleCcsICd1dGY4JykgKyBkZWNpcGhlci5maW5hbCgndXRmOCcpO1xuICB9XG5cbn0iXX0=