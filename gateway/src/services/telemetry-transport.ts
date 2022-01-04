import winston from 'winston';
import https from 'https';
import querystring from 'querystring';

export type LogCallback = (err: any, res: any) => void;

// Inherit from `winston-transport Http` so you can take advantage
// of the base functionality and `.exceptions.handle()`.
//
// Note: query and stream wouldn't work on this transport.
export class TelemetryTransport extends winston.transports.Http {
  private logInterval: number;
  private errorLogBuffer: string[];
  private requestCountAggregator: number;
  private instanceId: string;

  constructor(opts: any) {
    super(opts);

    this.logInterval = 3600000;
    this.instanceId = opts.instanceId || '';
    this.errorLogBuffer = [];
    this.requestCountAggregator = 0;
    setInterval(this.sendLogs.bind(this), this.logInterval);
  }

  private processData(log: any): void {
    if ('stack' in log)
      this.errorLogBuffer.push(`${Date.now()} - ${log.message}\n${log.stack}`);
    else if (log.level === 'http')
      this.requestCountAggregator += Number(log.message.split('\t')[1]);
  }

  public responseHandler(err: any, res: any): void {
    if (res && res.statusCode !== 200) {
      err = new Error(`Invalid HTTP Status Code: ${res.statusCode}`);
    }

    if (err) {
      this.emit('warn', err);
    } else {
      this.emit('logged', 'Successfully logged metrics.');
    }
  }

  public sendLogs(): void {
    if (this.errorLogBuffer.length > 0) {
      const logData = {
        data: JSON.stringify(this.errorLogBuffer),
        params: {
          ddtags: `instance_id:${this.instanceId},type:logs`,
          ddsource: 'gateway',
        },
      };
      this._request(logData, true, this.responseHandler.bind(this));
    }

    if (this.requestCountAggregator > 0) {
      const metric = {
        data: JSON.stringify({
          name: 'request_count',
          source: 'gateway',
          instance_id: this.instanceId,
          value: this.requestCountAggregator,
        }),
      };
      this._request(metric, false, this.responseHandler.bind(this));
    }

    this.errorLogBuffer = []; // reset error log buffer
    this.requestCountAggregator = 0; // reset request counter
  }

  public log(data: any, callback: LogCallback) {
    this.processData(data);

    if (callback) {
      setImmediate(callback);
    }
  }

  public _request(options: any, isLog: boolean, callback: LogCallback) {
    // Prepare options for outgoing HTTP request
    const headers = {
      'Content-Type': 'application/json',
      'Content-Length': options.data.length,
    };
    const req = https.request({
      method: 'POST',
      host: this.host,
      port: 443,
      path: isLog
        ? `/reporting-proxy-v2/log?${querystring.stringify(options.params)}`
        : '/reporting-proxy-v2/client_metrics',
      headers: headers,
    });

    req.on('error', callback);
    req.on('response', (res) =>
      res.on('end', () => callback(null, res)).resume()
    );
    req.end(Buffer.from(options.data, 'utf8'));
  }
}
