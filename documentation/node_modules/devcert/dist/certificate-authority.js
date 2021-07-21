"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const fs_1 = require("fs");
const debug_1 = tslib_1.__importDefault(require("debug"));
const constants_1 = require("./constants");
const platforms_1 = tslib_1.__importDefault(require("./platforms"));
const utils_1 = require("./utils");
const certificates_1 = require("./certificates");
const debug = debug_1.default('devcert:certificate-authority');
/**
 * Install the once-per-machine trusted root CA. We'll use this CA to sign
 * per-app certs.
 */
function installCertificateAuthority(options = {}) {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        debug(`Uninstalling existing certificates, which will be void once any existing CA is gone`);
        uninstall();
        constants_1.ensureConfigDirs();
        debug(`Making a temp working directory for files to copied in`);
        let rootKeyPath = utils_1.mktmp();
        debug(`Generating the OpenSSL configuration needed to setup the certificate authority`);
        seedConfigFiles();
        debug(`Generating a private key`);
        certificates_1.generateKey(rootKeyPath);
        debug(`Generating a CA certificate`);
        utils_1.openssl(['req', '-new', '-x509', '-config', constants_1.caSelfSignConfig, '-key', rootKeyPath, '-out', constants_1.rootCACertPath, '-days', '825']);
        debug('Saving certificate authority credentials');
        yield saveCertificateAuthorityCredentials(rootKeyPath);
        debug(`Adding the root certificate authority to trust stores`);
        yield platforms_1.default.addToTrustStores(constants_1.rootCACertPath, options);
    });
}
exports.default = installCertificateAuthority;
/**
 * Initializes the files OpenSSL needs to sign certificates as a certificate
 * authority, as well as our CA setup version
 */
function seedConfigFiles() {
    // This is v2 of the devcert certificate authority setup
    fs_1.writeFileSync(constants_1.caVersionFile, '2');
    // OpenSSL CA files
    fs_1.writeFileSync(constants_1.opensslDatabaseFilePath, '');
    fs_1.writeFileSync(constants_1.opensslSerialFilePath, '01');
}
function withCertificateAuthorityCredentials(cb) {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        debug(`Retrieving devcert's certificate authority credentials`);
        let tmpCAKeyPath = utils_1.mktmp();
        let caKey = yield platforms_1.default.readProtectedFile(constants_1.rootCAKeyPath);
        fs_1.writeFileSync(tmpCAKeyPath, caKey);
        yield cb({ caKeyPath: tmpCAKeyPath, caCertPath: constants_1.rootCACertPath });
        fs_1.unlinkSync(tmpCAKeyPath);
    });
}
exports.withCertificateAuthorityCredentials = withCertificateAuthorityCredentials;
function saveCertificateAuthorityCredentials(keypath) {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        debug(`Saving devcert's certificate authority credentials`);
        let key = fs_1.readFileSync(keypath, 'utf-8');
        yield platforms_1.default.writeProtectedFile(constants_1.rootCAKeyPath, key);
    });
}
function certErrors() {
    try {
        utils_1.openssl(['x509', '-in', constants_1.rootCACertPath, '-noout']);
        return '';
    }
    catch (e) {
        return e.toString();
    }
}
// This function helps to migrate from v1.0.x to >= v1.1.0.
/**
 * Smoothly migrate the certificate storage from v1.0.x to >= v1.1.0.
 * In v1.1.0 there are new options for retrieving the CA cert directly,
 * to help third-party Node apps trust the root CA.
 *
 * If a v1.0.x cert already exists, then devcert has written it with
 * platform.writeProtectedFile(), so an unprivileged readFile cannot access it.
 * Pre-detect and remedy this; it should only happen once per installation.
 */
function ensureCACertReadable(options = {}) {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        if (!certErrors()) {
            return;
        }
        /**
         * on windows, writeProtectedFile left the cert encrypted on *nix, the cert
         * has no read permissions either way, openssl will fail and that means we
         * have to fix it
         */
        try {
            const caFileContents = yield platforms_1.default.readProtectedFile(constants_1.rootCACertPath);
            platforms_1.default.deleteProtectedFiles(constants_1.rootCACertPath);
            fs_1.writeFileSync(constants_1.rootCACertPath, caFileContents);
        }
        catch (e) {
            return installCertificateAuthority(options);
        }
        // double check that we have a live one
        const remainingErrors = certErrors();
        if (remainingErrors) {
            return installCertificateAuthority(options);
        }
    });
}
exports.ensureCACertReadable = ensureCACertReadable;
/**
 * Remove as much of the devcert files and state as we can. This is necessary
 * when generating a new root certificate, and should be available to API
 * consumers as well.
 *
 * Not all of it will be removable. If certutil is not installed, we'll leave
 * Firefox alone. We try to remove files with maximum permissions, and if that
 * fails, we'll silently fail.
 *
 * It's also possible that the command to untrust will not work, and we'll
 * silently fail that as well; with no existing certificates anymore, the
 * security exposure there is minimal.
 */
function uninstall() {
    platforms_1.default.removeFromTrustStores(constants_1.rootCACertPath);
    platforms_1.default.deleteProtectedFiles(constants_1.domainsDir);
    platforms_1.default.deleteProtectedFiles(constants_1.rootCADir);
    platforms_1.default.deleteProtectedFiles(constants_1.getLegacyConfigDir());
}
exports.uninstall = uninstall;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2VydGlmaWNhdGUtYXV0aG9yaXR5LmpzIiwic291cmNlUm9vdCI6Ii9Vc2Vycy9qemV0bGVuL2dpdHMvZGV2Y2VydC8iLCJzb3VyY2VzIjpbImNlcnRpZmljYXRlLWF1dGhvcml0eS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFBQSwyQkFJWTtBQUNaLDBEQUFnQztBQUVoQywyQ0FXcUI7QUFDckIsb0VBQTBDO0FBQzFDLG1DQUF5QztBQUN6QyxpREFBNkM7QUFHN0MsTUFBTSxLQUFLLEdBQUcsZUFBVyxDQUFDLCtCQUErQixDQUFDLENBQUM7QUFFM0Q7OztHQUdHO0FBQ0gscUNBQTBELFVBQW1CLEVBQUU7O1FBQzdFLEtBQUssQ0FBQyxxRkFBcUYsQ0FBQyxDQUFDO1FBQzdGLFNBQVMsRUFBRSxDQUFDO1FBQ1osNEJBQWdCLEVBQUUsQ0FBQztRQUVuQixLQUFLLENBQUMsd0RBQXdELENBQUMsQ0FBQztRQUNoRSxJQUFJLFdBQVcsR0FBRyxhQUFLLEVBQUUsQ0FBQztRQUUxQixLQUFLLENBQUMsZ0ZBQWdGLENBQUMsQ0FBQztRQUN4RixlQUFlLEVBQUUsQ0FBQztRQUVsQixLQUFLLENBQUMsMEJBQTBCLENBQUMsQ0FBQztRQUNsQywwQkFBVyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1FBRXpCLEtBQUssQ0FBQyw2QkFBNkIsQ0FBQyxDQUFDO1FBQ3JDLGVBQU8sQ0FBQyxDQUFDLEtBQUssRUFBRSxNQUFNLEVBQUUsT0FBTyxFQUFFLFNBQVMsRUFBRSw0QkFBZ0IsRUFBRSxNQUFNLEVBQUUsV0FBVyxFQUFFLE1BQU0sRUFBRSwwQkFBYyxFQUFFLE9BQU8sRUFBRSxLQUFLLENBQUMsQ0FBQyxDQUFDO1FBRTVILEtBQUssQ0FBQywwQ0FBMEMsQ0FBQyxDQUFDO1FBQ2xELE1BQU0sbUNBQW1DLENBQUMsV0FBVyxDQUFDLENBQUM7UUFFdkQsS0FBSyxDQUFDLHVEQUF1RCxDQUFDLENBQUM7UUFDL0QsTUFBTSxtQkFBZSxDQUFDLGdCQUFnQixDQUFDLDBCQUFjLEVBQUUsT0FBTyxDQUFDLENBQUM7SUFDbEUsQ0FBQztDQUFBO0FBdEJELDhDQXNCQztBQUVEOzs7R0FHRztBQUNIO0lBQ0Usd0RBQXdEO0lBQ3hELGtCQUFTLENBQUMseUJBQWEsRUFBRSxHQUFHLENBQUMsQ0FBQztJQUM5QixtQkFBbUI7SUFDbkIsa0JBQVMsQ0FBQyxtQ0FBdUIsRUFBRSxFQUFFLENBQUMsQ0FBQztJQUN2QyxrQkFBUyxDQUFDLGlDQUFxQixFQUFFLElBQUksQ0FBQyxDQUFDO0FBQ3pDLENBQUM7QUFFRCw2Q0FBMEQsRUFBa0c7O1FBQzFKLEtBQUssQ0FBQyx3REFBd0QsQ0FBQyxDQUFDO1FBQ2hFLElBQUksWUFBWSxHQUFHLGFBQUssRUFBRSxDQUFDO1FBQzNCLElBQUksS0FBSyxHQUFHLE1BQU0sbUJBQWUsQ0FBQyxpQkFBaUIsQ0FBQyx5QkFBYSxDQUFDLENBQUM7UUFDbkUsa0JBQVMsQ0FBQyxZQUFZLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDL0IsTUFBTSxFQUFFLENBQUMsRUFBRSxTQUFTLEVBQUUsWUFBWSxFQUFFLFVBQVUsRUFBRSwwQkFBYyxFQUFFLENBQUMsQ0FBQztRQUNsRSxlQUFFLENBQUMsWUFBWSxDQUFDLENBQUM7SUFDbkIsQ0FBQztDQUFBO0FBUEQsa0ZBT0M7QUFFRCw2Q0FBbUQsT0FBZTs7UUFDaEUsS0FBSyxDQUFDLG9EQUFvRCxDQUFDLENBQUM7UUFDNUQsSUFBSSxHQUFHLEdBQUcsaUJBQVEsQ0FBQyxPQUFPLEVBQUUsT0FBTyxDQUFDLENBQUM7UUFDckMsTUFBTSxtQkFBZSxDQUFDLGtCQUFrQixDQUFDLHlCQUFhLEVBQUUsR0FBRyxDQUFDLENBQUM7SUFDL0QsQ0FBQztDQUFBO0FBR0Q7SUFDRSxJQUFJO1FBQ0YsZUFBTyxDQUFDLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSwwQkFBYyxFQUFFLFFBQVEsQ0FBQyxDQUFDLENBQUM7UUFDbkQsT0FBTyxFQUFFLENBQUM7S0FDWDtJQUFDLE9BQU8sQ0FBQyxFQUFFO1FBQ1YsT0FBTyxDQUFDLENBQUMsUUFBUSxFQUFFLENBQUM7S0FDckI7QUFDSCxDQUFDO0FBRUQsMkRBQTJEO0FBQzNEOzs7Ozs7OztHQVFHO0FBQ0gsOEJBQTJDLFVBQW1CLEVBQUU7O1FBQzlELElBQUksQ0FBQyxVQUFVLEVBQUUsRUFBRTtZQUNqQixPQUFPO1NBQ1I7UUFDRDs7OztXQUlHO1FBQ0gsSUFBSTtZQUNGLE1BQU0sY0FBYyxHQUFHLE1BQU0sbUJBQWUsQ0FBQyxpQkFBaUIsQ0FBQywwQkFBYyxDQUFDLENBQUM7WUFDL0UsbUJBQWUsQ0FBQyxvQkFBb0IsQ0FBQywwQkFBYyxDQUFDLENBQUM7WUFDckQsa0JBQVMsQ0FBQywwQkFBYyxFQUFFLGNBQWMsQ0FBQyxDQUFDO1NBQzNDO1FBQUMsT0FBTyxDQUFDLEVBQUU7WUFDVixPQUFPLDJCQUEyQixDQUFDLE9BQU8sQ0FBQyxDQUFDO1NBQzdDO1FBRUQsdUNBQXVDO1FBQ3ZDLE1BQU0sZUFBZSxHQUFHLFVBQVUsRUFBRSxDQUFDO1FBQ3JDLElBQUksZUFBZSxFQUFFO1lBQ25CLE9BQU8sMkJBQTJCLENBQUMsT0FBTyxDQUFDLENBQUM7U0FDN0M7SUFDSCxDQUFDO0NBQUE7QUF0QkQsb0RBc0JDO0FBRUQ7Ozs7Ozs7Ozs7OztHQVlHO0FBQ0g7SUFDRSxtQkFBZSxDQUFDLHFCQUFxQixDQUFDLDBCQUFjLENBQUMsQ0FBQztJQUN0RCxtQkFBZSxDQUFDLG9CQUFvQixDQUFDLHNCQUFVLENBQUMsQ0FBQztJQUNqRCxtQkFBZSxDQUFDLG9CQUFvQixDQUFDLHFCQUFTLENBQUMsQ0FBQztJQUNoRCxtQkFBZSxDQUFDLG9CQUFvQixDQUFDLDhCQUFrQixFQUFFLENBQUMsQ0FBQztBQUM3RCxDQUFDO0FBTEQsOEJBS0MiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICB1bmxpbmtTeW5jIGFzIHJtLFxuICByZWFkRmlsZVN5bmMgYXMgcmVhZEZpbGUsXG4gIHdyaXRlRmlsZVN5bmMgYXMgd3JpdGVGaWxlXG59IGZyb20gJ2ZzJztcbmltcG9ydCBjcmVhdGVEZWJ1ZyBmcm9tICdkZWJ1Zyc7XG5cbmltcG9ydCB7XG4gIGRvbWFpbnNEaXIsXG4gIHJvb3RDQURpcixcbiAgZW5zdXJlQ29uZmlnRGlycyxcbiAgZ2V0TGVnYWN5Q29uZmlnRGlyLFxuICByb290Q0FLZXlQYXRoLFxuICByb290Q0FDZXJ0UGF0aCxcbiAgY2FTZWxmU2lnbkNvbmZpZyxcbiAgb3BlbnNzbFNlcmlhbEZpbGVQYXRoLFxuICBvcGVuc3NsRGF0YWJhc2VGaWxlUGF0aCxcbiAgY2FWZXJzaW9uRmlsZVxufSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQgY3VycmVudFBsYXRmb3JtIGZyb20gJy4vcGxhdGZvcm1zJztcbmltcG9ydCB7IG9wZW5zc2wsIG1rdG1wIH0gZnJvbSAnLi91dGlscyc7XG5pbXBvcnQgeyBnZW5lcmF0ZUtleSB9IGZyb20gJy4vY2VydGlmaWNhdGVzJztcbmltcG9ydCB7IE9wdGlvbnMgfSBmcm9tICcuL2luZGV4JztcblxuY29uc3QgZGVidWcgPSBjcmVhdGVEZWJ1ZygnZGV2Y2VydDpjZXJ0aWZpY2F0ZS1hdXRob3JpdHknKTtcblxuLyoqXG4gKiBJbnN0YWxsIHRoZSBvbmNlLXBlci1tYWNoaW5lIHRydXN0ZWQgcm9vdCBDQS4gV2UnbGwgdXNlIHRoaXMgQ0EgdG8gc2lnblxuICogcGVyLWFwcCBjZXJ0cy5cbiAqL1xuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaW5zdGFsbENlcnRpZmljYXRlQXV0aG9yaXR5KG9wdGlvbnM6IE9wdGlvbnMgPSB7fSk6IFByb21pc2U8dm9pZD4ge1xuICBkZWJ1ZyhgVW5pbnN0YWxsaW5nIGV4aXN0aW5nIGNlcnRpZmljYXRlcywgd2hpY2ggd2lsbCBiZSB2b2lkIG9uY2UgYW55IGV4aXN0aW5nIENBIGlzIGdvbmVgKTtcbiAgdW5pbnN0YWxsKCk7XG4gIGVuc3VyZUNvbmZpZ0RpcnMoKTtcblxuICBkZWJ1ZyhgTWFraW5nIGEgdGVtcCB3b3JraW5nIGRpcmVjdG9yeSBmb3IgZmlsZXMgdG8gY29waWVkIGluYCk7XG4gIGxldCByb290S2V5UGF0aCA9IG1rdG1wKCk7XG5cbiAgZGVidWcoYEdlbmVyYXRpbmcgdGhlIE9wZW5TU0wgY29uZmlndXJhdGlvbiBuZWVkZWQgdG8gc2V0dXAgdGhlIGNlcnRpZmljYXRlIGF1dGhvcml0eWApO1xuICBzZWVkQ29uZmlnRmlsZXMoKTtcblxuICBkZWJ1ZyhgR2VuZXJhdGluZyBhIHByaXZhdGUga2V5YCk7XG4gIGdlbmVyYXRlS2V5KHJvb3RLZXlQYXRoKTtcblxuICBkZWJ1ZyhgR2VuZXJhdGluZyBhIENBIGNlcnRpZmljYXRlYCk7XG4gIG9wZW5zc2woWydyZXEnLCAnLW5ldycsICcteDUwOScsICctY29uZmlnJywgY2FTZWxmU2lnbkNvbmZpZywgJy1rZXknLCByb290S2V5UGF0aCwgJy1vdXQnLCByb290Q0FDZXJ0UGF0aCwgJy1kYXlzJywgJzgyNSddKTtcblxuICBkZWJ1ZygnU2F2aW5nIGNlcnRpZmljYXRlIGF1dGhvcml0eSBjcmVkZW50aWFscycpO1xuICBhd2FpdCBzYXZlQ2VydGlmaWNhdGVBdXRob3JpdHlDcmVkZW50aWFscyhyb290S2V5UGF0aCk7XG5cbiAgZGVidWcoYEFkZGluZyB0aGUgcm9vdCBjZXJ0aWZpY2F0ZSBhdXRob3JpdHkgdG8gdHJ1c3Qgc3RvcmVzYCk7XG4gIGF3YWl0IGN1cnJlbnRQbGF0Zm9ybS5hZGRUb1RydXN0U3RvcmVzKHJvb3RDQUNlcnRQYXRoLCBvcHRpb25zKTtcbn1cblxuLyoqXG4gKiBJbml0aWFsaXplcyB0aGUgZmlsZXMgT3BlblNTTCBuZWVkcyB0byBzaWduIGNlcnRpZmljYXRlcyBhcyBhIGNlcnRpZmljYXRlXG4gKiBhdXRob3JpdHksIGFzIHdlbGwgYXMgb3VyIENBIHNldHVwIHZlcnNpb25cbiAqL1xuZnVuY3Rpb24gc2VlZENvbmZpZ0ZpbGVzKCkge1xuICAvLyBUaGlzIGlzIHYyIG9mIHRoZSBkZXZjZXJ0IGNlcnRpZmljYXRlIGF1dGhvcml0eSBzZXR1cFxuICB3cml0ZUZpbGUoY2FWZXJzaW9uRmlsZSwgJzInKTtcbiAgLy8gT3BlblNTTCBDQSBmaWxlc1xuICB3cml0ZUZpbGUob3BlbnNzbERhdGFiYXNlRmlsZVBhdGgsICcnKTtcbiAgd3JpdGVGaWxlKG9wZW5zc2xTZXJpYWxGaWxlUGF0aCwgJzAxJyk7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB3aXRoQ2VydGlmaWNhdGVBdXRob3JpdHlDcmVkZW50aWFscyhjYjogKHsgY2FLZXlQYXRoLCBjYUNlcnRQYXRoIH06IHsgY2FLZXlQYXRoOiBzdHJpbmcsIGNhQ2VydFBhdGg6IHN0cmluZyB9KSA9PiBQcm9taXNlPHZvaWQ+IHwgdm9pZCkge1xuICBkZWJ1ZyhgUmV0cmlldmluZyBkZXZjZXJ0J3MgY2VydGlmaWNhdGUgYXV0aG9yaXR5IGNyZWRlbnRpYWxzYCk7XG4gIGxldCB0bXBDQUtleVBhdGggPSBta3RtcCgpO1xuICBsZXQgY2FLZXkgPSBhd2FpdCBjdXJyZW50UGxhdGZvcm0ucmVhZFByb3RlY3RlZEZpbGUocm9vdENBS2V5UGF0aCk7XG4gIHdyaXRlRmlsZSh0bXBDQUtleVBhdGgsIGNhS2V5KTtcbiAgYXdhaXQgY2IoeyBjYUtleVBhdGg6IHRtcENBS2V5UGF0aCwgY2FDZXJ0UGF0aDogcm9vdENBQ2VydFBhdGggfSk7XG4gIHJtKHRtcENBS2V5UGF0aCk7XG59XG5cbmFzeW5jIGZ1bmN0aW9uIHNhdmVDZXJ0aWZpY2F0ZUF1dGhvcml0eUNyZWRlbnRpYWxzKGtleXBhdGg6IHN0cmluZykge1xuICBkZWJ1ZyhgU2F2aW5nIGRldmNlcnQncyBjZXJ0aWZpY2F0ZSBhdXRob3JpdHkgY3JlZGVudGlhbHNgKTtcbiAgbGV0IGtleSA9IHJlYWRGaWxlKGtleXBhdGgsICd1dGYtOCcpO1xuICBhd2FpdCBjdXJyZW50UGxhdGZvcm0ud3JpdGVQcm90ZWN0ZWRGaWxlKHJvb3RDQUtleVBhdGgsIGtleSk7XG59XG5cblxuZnVuY3Rpb24gY2VydEVycm9ycygpOiBzdHJpbmcge1xuICB0cnkge1xuICAgIG9wZW5zc2woWyd4NTA5JywgJy1pbicsIHJvb3RDQUNlcnRQYXRoLCAnLW5vb3V0J10pO1xuICAgIHJldHVybiAnJztcbiAgfSBjYXRjaCAoZSkge1xuICAgIHJldHVybiBlLnRvU3RyaW5nKCk7XG4gIH1cbn1cblxuLy8gVGhpcyBmdW5jdGlvbiBoZWxwcyB0byBtaWdyYXRlIGZyb20gdjEuMC54IHRvID49IHYxLjEuMC5cbi8qKlxuICogU21vb3RobHkgbWlncmF0ZSB0aGUgY2VydGlmaWNhdGUgc3RvcmFnZSBmcm9tIHYxLjAueCB0byA+PSB2MS4xLjAuXG4gKiBJbiB2MS4xLjAgdGhlcmUgYXJlIG5ldyBvcHRpb25zIGZvciByZXRyaWV2aW5nIHRoZSBDQSBjZXJ0IGRpcmVjdGx5LFxuICogdG8gaGVscCB0aGlyZC1wYXJ0eSBOb2RlIGFwcHMgdHJ1c3QgdGhlIHJvb3QgQ0EuXG4gKiBcbiAqIElmIGEgdjEuMC54IGNlcnQgYWxyZWFkeSBleGlzdHMsIHRoZW4gZGV2Y2VydCBoYXMgd3JpdHRlbiBpdCB3aXRoXG4gKiBwbGF0Zm9ybS53cml0ZVByb3RlY3RlZEZpbGUoKSwgc28gYW4gdW5wcml2aWxlZ2VkIHJlYWRGaWxlIGNhbm5vdCBhY2Nlc3MgaXQuXG4gKiBQcmUtZGV0ZWN0IGFuZCByZW1lZHkgdGhpczsgaXQgc2hvdWxkIG9ubHkgaGFwcGVuIG9uY2UgcGVyIGluc3RhbGxhdGlvbi5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGVuc3VyZUNBQ2VydFJlYWRhYmxlKG9wdGlvbnM6IE9wdGlvbnMgPSB7fSk6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoIWNlcnRFcnJvcnMoKSkge1xuICAgIHJldHVybjtcbiAgfVxuICAvKipcbiAgICogb24gd2luZG93cywgd3JpdGVQcm90ZWN0ZWRGaWxlIGxlZnQgdGhlIGNlcnQgZW5jcnlwdGVkIG9uICpuaXgsIHRoZSBjZXJ0XG4gICAqIGhhcyBubyByZWFkIHBlcm1pc3Npb25zIGVpdGhlciB3YXksIG9wZW5zc2wgd2lsbCBmYWlsIGFuZCB0aGF0IG1lYW5zIHdlXG4gICAqIGhhdmUgdG8gZml4IGl0XG4gICAqL1xuICB0cnkge1xuICAgIGNvbnN0IGNhRmlsZUNvbnRlbnRzID0gYXdhaXQgY3VycmVudFBsYXRmb3JtLnJlYWRQcm90ZWN0ZWRGaWxlKHJvb3RDQUNlcnRQYXRoKTtcbiAgICBjdXJyZW50UGxhdGZvcm0uZGVsZXRlUHJvdGVjdGVkRmlsZXMocm9vdENBQ2VydFBhdGgpO1xuICAgIHdyaXRlRmlsZShyb290Q0FDZXJ0UGF0aCwgY2FGaWxlQ29udGVudHMpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgcmV0dXJuIGluc3RhbGxDZXJ0aWZpY2F0ZUF1dGhvcml0eShvcHRpb25zKTtcbiAgfVxuICBcbiAgLy8gZG91YmxlIGNoZWNrIHRoYXQgd2UgaGF2ZSBhIGxpdmUgb25lXG4gIGNvbnN0IHJlbWFpbmluZ0Vycm9ycyA9IGNlcnRFcnJvcnMoKTtcbiAgaWYgKHJlbWFpbmluZ0Vycm9ycykge1xuICAgIHJldHVybiBpbnN0YWxsQ2VydGlmaWNhdGVBdXRob3JpdHkob3B0aW9ucyk7XG4gIH1cbn1cblxuLyoqXG4gKiBSZW1vdmUgYXMgbXVjaCBvZiB0aGUgZGV2Y2VydCBmaWxlcyBhbmQgc3RhdGUgYXMgd2UgY2FuLiBUaGlzIGlzIG5lY2Vzc2FyeVxuICogd2hlbiBnZW5lcmF0aW5nIGEgbmV3IHJvb3QgY2VydGlmaWNhdGUsIGFuZCBzaG91bGQgYmUgYXZhaWxhYmxlIHRvIEFQSVxuICogY29uc3VtZXJzIGFzIHdlbGwuXG4gKiBcbiAqIE5vdCBhbGwgb2YgaXQgd2lsbCBiZSByZW1vdmFibGUuIElmIGNlcnR1dGlsIGlzIG5vdCBpbnN0YWxsZWQsIHdlJ2xsIGxlYXZlXG4gKiBGaXJlZm94IGFsb25lLiBXZSB0cnkgdG8gcmVtb3ZlIGZpbGVzIHdpdGggbWF4aW11bSBwZXJtaXNzaW9ucywgYW5kIGlmIHRoYXRcbiAqIGZhaWxzLCB3ZSdsbCBzaWxlbnRseSBmYWlsLlxuICogXG4gKiBJdCdzIGFsc28gcG9zc2libGUgdGhhdCB0aGUgY29tbWFuZCB0byB1bnRydXN0IHdpbGwgbm90IHdvcmssIGFuZCB3ZSdsbFxuICogc2lsZW50bHkgZmFpbCB0aGF0IGFzIHdlbGw7IHdpdGggbm8gZXhpc3RpbmcgY2VydGlmaWNhdGVzIGFueW1vcmUsIHRoZVxuICogc2VjdXJpdHkgZXhwb3N1cmUgdGhlcmUgaXMgbWluaW1hbC5cbiAqL1xuZXhwb3J0IGZ1bmN0aW9uIHVuaW5zdGFsbCgpOiB2b2lkIHtcbiAgY3VycmVudFBsYXRmb3JtLnJlbW92ZUZyb21UcnVzdFN0b3Jlcyhyb290Q0FDZXJ0UGF0aCk7XG4gIGN1cnJlbnRQbGF0Zm9ybS5kZWxldGVQcm90ZWN0ZWRGaWxlcyhkb21haW5zRGlyKTtcbiAgY3VycmVudFBsYXRmb3JtLmRlbGV0ZVByb3RlY3RlZEZpbGVzKHJvb3RDQURpcik7XG4gIGN1cnJlbnRQbGF0Zm9ybS5kZWxldGVQcm90ZWN0ZWRGaWxlcyhnZXRMZWdhY3lDb25maWdEaXIoKSk7XG59Il19