"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const password_prompt_1 = tslib_1.__importDefault(require("password-prompt"));
const utils_1 = require("./utils");
const DefaultUI = {
    getWindowsEncryptionPassword() {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            return yield password_prompt_1.default('devcert password (http://bit.ly/devcert-what-password?):');
        });
    },
    warnChromeOnLinuxWithoutCertutil() {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            console.warn(`
      WARNING: It looks like you have Chrome installed, but you specified
      'skipCertutilInstall: true'. Unfortunately, without installing
      certutil, it's impossible get Chrome to trust devcert's certificates
      The certificates will work, but Chrome will continue to warn you that
      they are untrusted.
    `);
        });
    },
    closeFirefoxBeforeContinuing() {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            console.log('Please close Firefox before continuing');
        });
    },
    startFirefoxWizard(certificateHost) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            console.log(`
      devcert was unable to automatically configure Firefox. You'll need to
      complete this process manually. Don't worry though - Firefox will walk
      you through it.

      When you're ready, hit any key to continue. Firefox will launch and
      display a wizard to walk you through how to trust the devcert
      certificate. When you are finished, come back here and we'll finish up.

      (If Firefox doesn't start, go ahead and start it and navigate to
      ${certificateHost} in a new tab.)

      If you are curious about why all this is necessary, check out
      https://github.com/davewasmer/devcert#how-it-works

      <Press any key to launch Firefox wizard>
    `);
            yield utils_1.waitForUser();
        });
    },
    firefoxWizardPromptPage(certificateURL) {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            return `
      <html>
        <head>
          <meta http-equiv="refresh" content="0; url=${certificateURL}" />
        </head>
      </html>
    `;
        });
    },
    waitForFirefoxWizard() {
        return tslib_1.__awaiter(this, void 0, void 0, function* () {
            console.log(`
      Launching Firefox ...

      Great! Once you've finished the Firefox wizard for adding the devcert
      certificate, just hit any key here again and we'll wrap up.

      <Press any key to continue>
    `);
            yield utils_1.waitForUser();
        });
    }
};
exports.default = DefaultUI;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlci1pbnRlcmZhY2UuanMiLCJzb3VyY2VSb290IjoiL1VzZXJzL2p6ZXRsZW4vZ2l0cy9kZXZjZXJ0LyIsInNvdXJjZXMiOlsidXNlci1pbnRlcmZhY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsOEVBQTZDO0FBQzdDLG1DQUFzQztBQVd0QyxNQUFNLFNBQVMsR0FBa0I7SUFDekIsNEJBQTRCOztZQUNoQyxPQUFPLE1BQU0seUJBQWMsQ0FBQywwREFBMEQsQ0FBQyxDQUFDO1FBQzFGLENBQUM7S0FBQTtJQUNLLGdDQUFnQzs7WUFDcEMsT0FBTyxDQUFDLElBQUksQ0FBQzs7Ozs7O0tBTVosQ0FBQyxDQUFDO1FBQ0wsQ0FBQztLQUFBO0lBQ0ssNEJBQTRCOztZQUNoQyxPQUFPLENBQUMsR0FBRyxDQUFDLHdDQUF3QyxDQUFDLENBQUM7UUFDeEQsQ0FBQztLQUFBO0lBQ0ssa0JBQWtCLENBQUMsZUFBZTs7WUFDdEMsT0FBTyxDQUFDLEdBQUcsQ0FBQzs7Ozs7Ozs7OztRQVVQLGVBQWdCOzs7Ozs7S0FNcEIsQ0FBQyxDQUFDO1lBQ0gsTUFBTSxtQkFBVyxFQUFFLENBQUM7UUFDdEIsQ0FBQztLQUFBO0lBQ0ssdUJBQXVCLENBQUMsY0FBc0I7O1lBQ2xELE9BQU87Ozt1REFHNEMsY0FBYzs7O0tBR2hFLENBQUM7UUFDSixDQUFDO0tBQUE7SUFDSyxvQkFBb0I7O1lBQ3hCLE9BQU8sQ0FBQyxHQUFHLENBQUM7Ozs7Ozs7S0FPWCxDQUFDLENBQUE7WUFDRixNQUFNLG1CQUFXLEVBQUUsQ0FBQztRQUN0QixDQUFDO0tBQUE7Q0FDRixDQUFBO0FBRUQsa0JBQWUsU0FBUyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHBhc3N3b3JkUHJvbXB0IGZyb20gJ3Bhc3N3b3JkLXByb21wdCc7XG5pbXBvcnQgeyB3YWl0Rm9yVXNlciB9IGZyb20gJy4vdXRpbHMnO1xuXG5leHBvcnQgaW50ZXJmYWNlIFVzZXJJbnRlcmZhY2Uge1xuICBnZXRXaW5kb3dzRW5jcnlwdGlvblBhc3N3b3JkKCk6IFByb21pc2U8c3RyaW5nPjtcbiAgd2FybkNocm9tZU9uTGludXhXaXRob3V0Q2VydHV0aWwoKTogUHJvbWlzZTx2b2lkPjtcbiAgY2xvc2VGaXJlZm94QmVmb3JlQ29udGludWluZygpOiBQcm9taXNlPHZvaWQ+O1xuICBzdGFydEZpcmVmb3hXaXphcmQoY2VydGlmaWNhdGVIb3N0OiBzdHJpbmcpOiBQcm9taXNlPHZvaWQ+O1xuICBmaXJlZm94V2l6YXJkUHJvbXB0UGFnZShjZXJ0aWZpY2F0ZVVSTDogc3RyaW5nKTogUHJvbWlzZTxzdHJpbmc+O1xuICB3YWl0Rm9yRmlyZWZveFdpemFyZCgpOiBQcm9taXNlPHZvaWQ+O1xufVxuXG5jb25zdCBEZWZhdWx0VUk6IFVzZXJJbnRlcmZhY2UgPSB7XG4gIGFzeW5jIGdldFdpbmRvd3NFbmNyeXB0aW9uUGFzc3dvcmQoKSB7XG4gICAgcmV0dXJuIGF3YWl0IHBhc3N3b3JkUHJvbXB0KCdkZXZjZXJ0IHBhc3N3b3JkIChodHRwOi8vYml0Lmx5L2RldmNlcnQtd2hhdC1wYXNzd29yZD8pOicpO1xuICB9LFxuICBhc3luYyB3YXJuQ2hyb21lT25MaW51eFdpdGhvdXRDZXJ0dXRpbCgpIHtcbiAgICBjb25zb2xlLndhcm4oYFxuICAgICAgV0FSTklORzogSXQgbG9va3MgbGlrZSB5b3UgaGF2ZSBDaHJvbWUgaW5zdGFsbGVkLCBidXQgeW91IHNwZWNpZmllZFxuICAgICAgJ3NraXBDZXJ0dXRpbEluc3RhbGw6IHRydWUnLiBVbmZvcnR1bmF0ZWx5LCB3aXRob3V0IGluc3RhbGxpbmdcbiAgICAgIGNlcnR1dGlsLCBpdCdzIGltcG9zc2libGUgZ2V0IENocm9tZSB0byB0cnVzdCBkZXZjZXJ0J3MgY2VydGlmaWNhdGVzXG4gICAgICBUaGUgY2VydGlmaWNhdGVzIHdpbGwgd29yaywgYnV0IENocm9tZSB3aWxsIGNvbnRpbnVlIHRvIHdhcm4geW91IHRoYXRcbiAgICAgIHRoZXkgYXJlIHVudHJ1c3RlZC5cbiAgICBgKTtcbiAgfSxcbiAgYXN5bmMgY2xvc2VGaXJlZm94QmVmb3JlQ29udGludWluZygpIHtcbiAgICBjb25zb2xlLmxvZygnUGxlYXNlIGNsb3NlIEZpcmVmb3ggYmVmb3JlIGNvbnRpbnVpbmcnKTtcbiAgfSxcbiAgYXN5bmMgc3RhcnRGaXJlZm94V2l6YXJkKGNlcnRpZmljYXRlSG9zdCkge1xuICAgIGNvbnNvbGUubG9nKGBcbiAgICAgIGRldmNlcnQgd2FzIHVuYWJsZSB0byBhdXRvbWF0aWNhbGx5IGNvbmZpZ3VyZSBGaXJlZm94LiBZb3UnbGwgbmVlZCB0b1xuICAgICAgY29tcGxldGUgdGhpcyBwcm9jZXNzIG1hbnVhbGx5LiBEb24ndCB3b3JyeSB0aG91Z2ggLSBGaXJlZm94IHdpbGwgd2Fsa1xuICAgICAgeW91IHRocm91Z2ggaXQuXG5cbiAgICAgIFdoZW4geW91J3JlIHJlYWR5LCBoaXQgYW55IGtleSB0byBjb250aW51ZS4gRmlyZWZveCB3aWxsIGxhdW5jaCBhbmRcbiAgICAgIGRpc3BsYXkgYSB3aXphcmQgdG8gd2FsayB5b3UgdGhyb3VnaCBob3cgdG8gdHJ1c3QgdGhlIGRldmNlcnRcbiAgICAgIGNlcnRpZmljYXRlLiBXaGVuIHlvdSBhcmUgZmluaXNoZWQsIGNvbWUgYmFjayBoZXJlIGFuZCB3ZSdsbCBmaW5pc2ggdXAuXG5cbiAgICAgIChJZiBGaXJlZm94IGRvZXNuJ3Qgc3RhcnQsIGdvIGFoZWFkIGFuZCBzdGFydCBpdCBhbmQgbmF2aWdhdGUgdG9cbiAgICAgICR7IGNlcnRpZmljYXRlSG9zdCB9IGluIGEgbmV3IHRhYi4pXG5cbiAgICAgIElmIHlvdSBhcmUgY3VyaW91cyBhYm91dCB3aHkgYWxsIHRoaXMgaXMgbmVjZXNzYXJ5LCBjaGVjayBvdXRcbiAgICAgIGh0dHBzOi8vZ2l0aHViLmNvbS9kYXZld2FzbWVyL2RldmNlcnQjaG93LWl0LXdvcmtzXG5cbiAgICAgIDxQcmVzcyBhbnkga2V5IHRvIGxhdW5jaCBGaXJlZm94IHdpemFyZD5cbiAgICBgKTtcbiAgICBhd2FpdCB3YWl0Rm9yVXNlcigpO1xuICB9LFxuICBhc3luYyBmaXJlZm94V2l6YXJkUHJvbXB0UGFnZShjZXJ0aWZpY2F0ZVVSTDogc3RyaW5nKSB7XG4gICAgcmV0dXJuIGBcbiAgICAgIDxodG1sPlxuICAgICAgICA8aGVhZD5cbiAgICAgICAgICA8bWV0YSBodHRwLWVxdWl2PVwicmVmcmVzaFwiIGNvbnRlbnQ9XCIwOyB1cmw9JHtjZXJ0aWZpY2F0ZVVSTH1cIiAvPlxuICAgICAgICA8L2hlYWQ+XG4gICAgICA8L2h0bWw+XG4gICAgYDtcbiAgfSxcbiAgYXN5bmMgd2FpdEZvckZpcmVmb3hXaXphcmQoKSB7XG4gICAgY29uc29sZS5sb2coYFxuICAgICAgTGF1bmNoaW5nIEZpcmVmb3ggLi4uXG5cbiAgICAgIEdyZWF0ISBPbmNlIHlvdSd2ZSBmaW5pc2hlZCB0aGUgRmlyZWZveCB3aXphcmQgZm9yIGFkZGluZyB0aGUgZGV2Y2VydFxuICAgICAgY2VydGlmaWNhdGUsIGp1c3QgaGl0IGFueSBrZXkgaGVyZSBhZ2FpbiBhbmQgd2UnbGwgd3JhcCB1cC5cblxuICAgICAgPFByZXNzIGFueSBrZXkgdG8gY29udGludWU+XG4gICAgYClcbiAgICBhd2FpdCB3YWl0Rm9yVXNlcigpO1xuICB9XG59XG5cbmV4cG9ydCBkZWZhdWx0IERlZmF1bHRVSTsiXX0=