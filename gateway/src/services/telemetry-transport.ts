import winston from 'winston';
import https from 'https';

export type LogCallback = (err: any, res: any) => void;

// Inherit from `winston-transport Http` so you can take advantage
// of the base functionality and `.exceptions.handle()`.
//
// Note: query and stream wouldn't work on this transport.
export class TelemetryTransport extends winston.transports.Http {
  private logInterval: number;
  private logBuffer: any[];

  constructor(opts: any) {
    super(opts);

    this.logInterval = opts.interval || 3600000;
    this.logBuffer = [];
    setInterval(this.sendLogs.bind(this), this.logInterval);
  }

  private processLog(log: any): void {
    if ('stack' in log)
      this.logBuffer.push(`${Date.now()} - ${log.message}\n${log.stack}`);
    else this.logBuffer.push(`${Date.now()} - ${log.message}`);
  }

  public sendLogs(): void {
    if (this.logBuffer.length > 0) {
      this._request(
        {
          data: JSON.stringify(this.logBuffer),
          params: { ddtags: 'type:logs', ddsource: 'gateway' },
        },
        (err: any, res: any) => {
          if (res && res.statusCode !== 200) {
            err = new Error(`Invalid HTTP Status Code: ${res.statusCode}`);
          }

          if (err) {
            this.emit('warn', err);
          } else {
            this.emit('logged', 'Successfully logged metrics.');
          }
        }
      );

      this.logBuffer = []; // reset buffer
    }
  }

  public log(info: any, callback: LogCallback) {
    this.processLog(info);

    if (callback) {
      setImmediate(callback);
    }
  }

  public _request(options: any, callback: LogCallback) {
    // Prepare options for outgoing HTTP request
    const headers = { 'content-type': 'application/json' };
    const req = https.request({
      ...options,
      method: 'POST',
      host: this.host,
      port: 443,
      path: '',
      headers: headers,
      auth: '',
      agent: this.agent,
    });

    req.on('error', callback);
    req.on('response', (res) =>
      res.on('end', () => callback(null, res)).resume()
    );
    req.end(Buffer.from(JSON.stringify(options), 'utf8'));
  }
}
