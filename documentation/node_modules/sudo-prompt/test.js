var fs = require('fs');
var sudo = require('./');
var exec = require('child_process').exec;

function kill(end) {
  if (process.platform === 'win32') return end();
  exec('sudo -k', end);
}

function icns() {
  if (process.platform !== 'darwin') return undefined;
  var path = '/Applications/Electron.app/Contents/Resources/Electron.icns';
  try {
    fs.statSync(path);
    return path;
  } catch (error) {}
  return undefined;
}

kill(
  function() {
    var options = {
      icns: icns(),
      name: 'Electron'
    };
    var command = 'echo hello';
    if (process.platform === 'win32') {
      var expected = 'hello\r\n';
    } else {
      var expected = 'hello\n';
    }
    console.log('sudo.exec(' + JSON.stringify(command) + ', ' + JSON.stringify(options) + ')');
    sudo.exec(command, options,
      function(error, stdout, stderr) {
        console.log('error: ' + error);
        console.log('stdout: ' + JSON.stringify(stdout));
        console.log('stderr: ' + JSON.stringify(stderr));
        kill(
          function() {
            if (error) throw error;
            if (stdout !== expected) {
              throw new Error('stdout != ' + JSON.stringify(expected));
            }
            if (stderr !== "") throw new Error('stderr != ""');
            console.log('OK');
          }
        );
      }
    );
  }
);
