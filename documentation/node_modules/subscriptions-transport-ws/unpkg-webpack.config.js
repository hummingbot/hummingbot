var path = require('path');

module.exports = {
  context: path.join(__dirname, '/dist'),
  entry: './client.js',
  output: {
    path: path.join(__dirname, '/browser'),
    filename: 'client.js',
    library: 'SubscriptionsTransportWs'
  }
};
