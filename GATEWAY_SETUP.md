# Gateway Setup Guide

This guide covers the installation, configuration, and usage of Hummingbot Gateway v2.7.

## Table of Contents
- [Changes from v2.6](#changes-from-v26)
- [Installation](#installation)
- [Configuration](#configuration)
- [Wallet Management](#wallet-management)
- [Gateway Commands](#gateway-commands)
- [Connecting to DEXs](#connecting-to-dexs)
- [Secure Gateway behind SSL](#secure-gateway-behind-ssl)
- [Troubleshooting](#troubleshooting)

## Changes from v2.6

Gateway v2.7 introduces significant architectural improvements for better performance, reliability, and ease of use:

### Major Architectural Changes

1. **Centralized Wallet Management**
   - Wallets are now connected to **chains**, not individual connectors
   - One wallet per chain is used across all DEX connectors on that chain
   - Example: A single Ethereum wallet works for Uniswap, SushiSwap, and all other Ethereum DEXs
   - Wallet addresses are no longer stored in `gateway_connections.json`

2. **Improved Gateway HTTP Client**
   - Single consolidated `GatewayHttpClient` for all Gateway interactions
   - Automatic gateway state initialization on startup
   - Built-in caching for wallets, connectors, and chains
   - Better error handling and rate limit management

3. **Enhanced Transaction Handling**
   - Transactions now use a "send and poll for hash" approach instead of black box execution
   - Dynamic fee control with automatic 2x multiplier on retries
   - Non-blocking transaction execution with background retry logic
   - Fee estimate caching for improved performance
   - More transparent transaction status tracking

4. **New Wallet Commands**
   - `gateway wallet add <chain>` - Add a wallet for a specific chain
   - `gateway wallet list [chain]` - List all wallets or filter by chain
   - `gateway wallet remove <chain> <address>` - Remove a wallet from a chain

5. **Removed Commands & Features**
   - `gateway connect <connector>` - No longer needed; connectors auto-detect wallets
   - `gateway connector-tokens` - Token management is now automatic
   - Per-DEX wallet configuration - Replaced by chain-based wallets
   - Legacy transaction tracking systems

### Technical Improvements

- Gateway modules moved from `core/gateway` to `connector/gateway`
- Simplified connector detection and initialization
- 5-minute TTL cache for dynamic wallet resolution
- Support for both HTTP and HTTPS modes with `gateway_use_ssl` configuration
- Improved error messages and debugging capabilities

### Migration from v2.6

If upgrading from v2.6:
1. Add wallets for each chain you plan to use:
   ```bash
   >>> gateway wallet add ethereum
   >>> gateway wallet add solana
   ```
2. Remove any connector-specific configurations from `gateway_connections.json`
3. Connectors will automatically use the first available wallet for their chain
4. Review and update any custom scripts that relied on the old transaction handling

## Installation

Gateway is now included as a Git submodule in Hummingbot. There are several ways to install it:

> **Note**: The `gateway-setup.sh` script automates configuration setup and certificate linking, making it easier to get Gateway running with Hummingbot.

### Option 1: Install from Source

#### New Installation
```bash
# Clone Hummingbot with Gateway included
git clone --recurse-submodules https://github.com/hummingbot/hummingbot.git
cd hummingbot

# Install Hummingbot dependencies
./install

# Install Gateway dependencies
cd gateway
yarn install

# Run Gateway setup script
./gateway-setup.sh

# The setup script will ask:
# 1. "Do you want to link to Hummingbot client certificates (Y/N) >>>"
#    - Answer Y to automatically link certificates from Hummingbot
#    - This creates a symlink from gateway/certs to hummingbot/certs
# 2. "Enter path to the Hummingbot certs folder (press Enter for default) >>>"
#    - Press Enter to use default path: ../certs
#    - Or specify a custom path if your certs are elsewhere
# 3. The script will then show what it will do and ask for confirmation

cd ..

# Start Gateway (in a separate terminal)
cd gateway
yarn start --dev

# Start Hummingbot
./start
```

#### Update Existing Installation
```bash
# If you already have Hummingbot cloned
cd hummingbot

# Update to latest code
git pull

# Initialize and update Gateway submodule
git submodule update --init --recursive

# To update Gateway to latest version in the future
git submodule update --remote --merge
```

### Option 2: Install with Docker

#### Using Pre-built Images
To use the official Docker images from Docker Hub:

1. **Edit docker-compose.yml** to uncomment the Gateway service (keep the default image configuration)

#### Building from Local Source
To build and use Docker images from your local source code:

1. **Edit docker-compose.yml** to build from local source:
```yaml
services:
  hummingbot:
    container_name: hummingbot
    # Comment out the image line and uncomment build section
    # image: hummingbot/hummingbot:latest
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./conf:/home/hummingbot/conf
      - ./logs:/home/hummingbot/logs
      - ./data:/home/hummingbot/data
      - ./certs:/home/hummingbot/certs
      - ./scripts:/home/hummingbot/scripts
    tty: true
    stdin_open: true
    network_mode: host

  gateway:
    restart: always
    container_name: gateway
    # Comment out the image line and add build section
    # image: hummingbot/gateway:latest
    build:
      context: ./gateway
      dockerfile: Dockerfile
    ports:
      - "15888:15888"
      - "8080:8080"
    volumes:
      - "./gateway_files/conf:/home/gateway/conf"
      - "./gateway_files/logs:/home/gateway/logs"
      - "./gateway_files/db:/home/gateway/db"
      - "./certs:/home/gateway/certs"
    environment:
      - GATEWAY_PASSPHRASE=a  # Set your passphrase here
```

2. **Build the Docker images**:
```bash
# Build both images
docker compose build

# Or build individually
docker compose build hummingbot
docker compose build gateway
```

3. **Start both services**:
```bash
# Start both Hummingbot and Gateway
docker compose up -d

# Connect to Hummingbot
docker attach hummingbot
```

> **Note**: When building from source, Docker will use your local code changes. This is useful for testing modifications or using the latest development version.

### Option 3: Separate Hummingbot and Gateway Installs
For advanced users who want to run Hummingbot and Gateway independently:

#### Install Hummingbot
```bash
# Clone Hummingbot without submodules
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot
./install  # Follow the installation prompts
```

#### Install Gateway Separately
```bash
# In a different directory, clone Gateway
git clone https://github.com/hummingbot/gateway.git
cd gateway

# Install dependencies
yarn install

# Run the setup script
./gateway-setup.sh

# When running in separate mode, the script will:
# 1. Ask if you want to link certificates
# 2. Copy configuration templates to conf/
# 3. Set up the necessary folder structure
```

#### Start Services
```bash
# Start Gateway (in Gateway directory)
cd gateway
yarn start --dev

# In separate terminal, start Hummingbot
cd hummingbot
./start
```

Note: Ensure both services are configured to use the same host and port settings.

## Configuration

By default, Gateway runs in unencrypted mode for easier setup and development. The default configuration in `conf/conf_client.yml` is:

```yaml
gateway:
  gateway_api_host: localhost
  gateway_api_port: '15888'
  gateway_use_ssl: false      # Default: false for easier setup
```

This configuration works out of the box with the `yarn start --dev` command. No certificates are required for basic operation.

## Wallet Management

Gateway v2.7 introduces centralized wallet management. Wallets are now managed per chain, not per connector.

### Add a Wallet
```bash
>>> gateway wallet add <chain>

# Example:
>>> gateway wallet add ethereum
Enter private key: ****
Wallet added successfully: 0x1234...5678
```

### List Wallets
```bash
# List all wallets
>>> gateway wallet list

# List wallets for specific chain
>>> gateway wallet list ethereum
```

### Remove a Wallet
```bash
>>> gateway wallet remove <chain> <address>

# Example:
>>> gateway wallet remove ethereum 0x1234...5678
```

### Important Notes:
- Wallets are stored in Gateway at `/gateway/conf/wallets/{chain}/`
- The first wallet for each chain is used as default
- Connectors automatically use the appropriate wallet for their chain
- No need to select wallet when connecting to DEXs

## Gateway Commands

### Status and Connectivity
```bash
# Check Gateway status
>>> gateway status

# Test connectivity and network latency
>>> gateway ping

# List available DEX connectors
>>> gateway list
```

### Balance Commands
```bash
# Check all balances
>>> gateway balance

# Check balances for specific chain
>>> gateway balance ethereum

# Check balances for specific network
>>> gateway balance ethereum mainnet

# Check specific tokens
>>> gateway balance ethereum mainnet 0x1234...5678 ETH,USDC,WETH
```

### Token Management
```bash
# Check token allowances
>>> gateway allowance <network> <connector>

# Example:
>>> gateway allowance ethereum-mainnet uniswap

# Approve tokens for spending
>>> gateway approve <network> <connector> <tokens>

# Example:
>>> gateway approve ethereum-mainnet uniswap USDC,WETH
```

### Token Wrapping
```bash
# Wrap native tokens (ETH → WETH, BNB → WBNB)
>>> gateway wrap <network> <amount>

# Example:
>>> gateway wrap ethereum-mainnet 1.5
```

### Configuration
```bash
# View all Gateway configuration
>>> gateway config

# View specific configuration
>>> gateway config <key>

# Update configuration
>>> gateway config <key> <value>
```

## Connecting to DEXs

### List DEX Connectors
```bash
>>> gateway list
```

## Secure Gateway behind SSL

For production environments or when additional security is required, you can enable SSL encryption between Hummingbot and Gateway.

### Docker Compose Configuration

By default, Gateway runs in development mode (HTTP) when using Docker Compose. To switch between secure and non-secure modes:

#### Non-SSL Mode (Development)
In `docker-compose.yml`, add the `DEV=true` environment variable:
```yaml
  gateway:
    restart: always
    container_name: gateway
    environment:
      - GATEWAY_PASSPHRASE=a
      - DEV=true  # Run in dev mode without SSL certificates
```

This allows Gateway to run without certificates, perfect for development and testing.

Ensure Hummingbot's configuration matches in `conf/conf_client.yml`:
```yaml
gateway:
  gateway_api_host: localhost
  gateway_api_port: '15888'
  gateway_use_ssl: false  # Must be false for dev mode
```

#### SSL Mode (Production)
For production use, remove or set `DEV=false`:
```yaml
  gateway:
    restart: always
    container_name: gateway
    environment:
      - GATEWAY_PASSPHRASE=a
      - DEV=false  # Or remove this line entirely
```

When running in SSL mode, you must:
1. Generate certificates first (see below)
2. Update Hummingbot's configuration in `conf/conf_client.yml`:
   ```yaml
   gateway:
     gateway_api_host: localhost
     gateway_api_port: '15888'
     gateway_use_ssl: true  # Must be true for SSL mode
   ```

### Enable SSL Mode

1. **Generate Certificates in Hummingbot**:
```bash
# In Hummingbot CLI
>>> generate_certs
```

This command will:
- Prompt for a passphrase (or use your client password)
- Create certificates in `certs/` directory
- Generate the following files:
  - `ca_cert.pem` - Certificate Authority certificate
  - `ca_key.pem` - Certificate Authority private key
  - `server_cert.pem` - Server certificate
  - `server_key.pem` - Server private key
  - `client_cert.pem` - Client certificate
  - `client_key.pem` - Client private key

2. **Configure Certificate Sharing**:

For submodule installations, certificates are automatically shared via symlinks.

For separate installations:
```bash
# Copy certificates from Hummingbot to Gateway
cp -r /path/to/hummingbot/certs/* /path/to/gateway/certs/

# Or create symlinks
ln -s /path/to/hummingbot/certs /path/to/gateway/certs
```

3. **Update Hummingbot Configuration**:

Edit `conf/conf_client.yml`:
```yaml
gateway:
  gateway_api_host: localhost
  gateway_api_port: '15888'
  gateway_use_ssl: true      # Enable SSL

certs_path: /path/to/hummingbot/certs
```

4. **Start Gateway with SSL**:
```bash
# Start Gateway in production mode (with SSL)
yarn start

# Note: Do NOT use --dev flag when SSL is enabled
```

### SSL Best Practices
- Keep your private keys secure and never share them
- Use strong passphrases for certificate generation
- Regularly rotate certificates in production environments
- Ensure proper file permissions on certificate files (readable only by service user)

## Troubleshooting

### Common Issues

#### "No wallet found for chain"
Add a wallet for the required chain:
```bash
>>> gateway wallet add <chain>
```

#### Certificate Errors (SSL Mode Only)
If you've enabled SSL mode and encounter certificate errors:
1. Verify SSL is enabled in both Hummingbot and Gateway
2. See the [Secure Gateway behind SSL](#secure-gateway-behind-ssl) section for proper setup
3. Ensure `gateway_use_ssl: true` in your configuration
4. Start Gateway without `--dev` flag when SSL is enabled

#### Connection Refused
1. Verify Gateway is running:
   ```bash
   # In Gateway directory
   yarn start --dev
   ```
2. Check port 15888 is not blocked
3. Verify `gateway_api_host` and `gateway_api_port` in configuration

#### Rate Limit Errors
Gateway v2.7 includes automatic retry logic for rate limits. If issues persist:
1. Reduce request frequency
2. Check specific chain RPC endpoint limits
3. Consider using alternative RPC endpoints

### Debug Mode
For detailed logging:
```bash
# In Gateway
DEBUG=* yarn start --dev
```
