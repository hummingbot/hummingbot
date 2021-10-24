*Originally published in the Hummingbot blog: [part 1](https://hummingbot.io/blog/gateway-v2-code-architecture), [part 2](https://hummingbot.io/blog/gateway-architecture-part-2)*

## Introduction

Hummingbot Gateway is middleware that allows Hummingbot to connect to decentralized exchanges like Uniswap. Gateway V1 is currently in a separate Github repository (https://github.com/coinalpha/gateway-api), while Gateway V2 will be contained in a `gateway` directory in the Hummingbot repository.

Gateway is a separate piece of software apart from Hummingbot, because software libraries needed for accessing decentralized exchanges, e.g. the Uniswap Smart Order Router, are usually not written in Python. Gateway provides Hummingbot access to these decentralized exchanges with their differing software stacks, by exposing a secure and unified API interface to Hummingbot. This API interface can also be used by other potential gateway clients, such as proprietary trading software.

In this series of Hummingbot Gateway v2 Architecture blog posts, we will outline the architectural changes we will be making to Gateway v2 to bring it up to production quality - and why the changes are needed.

## History

Hummingbot Gateway was originally conceived as an interface for Hummingbot to interact with Celo, Balancer and Terra around mid 2020. While the concept of decentralized exchanges were already well known at the time, trading activity was relatively nascent compared to now.

As a result, the original Hummingbot Gateway had a relatively simple architecture, and did not account for many of the failure modes seen in modern DEXes like Uniswap. e.g. stuck blockchain transactions. As a result, the original Hummingbot Gateway could not provide the reliability expected of production trading systems.

We decided to do a major overhaul of the Hummingbot Gateway architecture in Q3 2020. The redesigned Hummingbot Gateway will be called **Gateway v2**.

## Gateway V2

Gateway v2 is a redesign of the original Hummingbot Gateway, with the following design goals:

* **Robustness and reliability:** Gateway should continue to work despite encountering errors and failures; and when an operation in the gateway has to fail, it should fail gracefully rather than catastrophically.

* **User experience:** Gateway should be easy to set up and configure; once the gateway has been set up, it should work reliably in the background and let the user focus on trading.

* **Developer experience:** While the initial versions of gateway v2 will come with some decentralized exchange connectors bundled with it, we expect the community will be making the majority of contributions for DEX connectors, feature requests and bug fixes over time. This means gateway v2 should be easy to develop and test on for community developers.

## Robustness and Reliability

Hummingbot gateway and Hummingbot itself, are more similar to backend systems than frontend systems in nature. In particular, these systems deal with transactions that can have significant financial consequences. Thus, Hummingbot gateway needs to be built with the same or superior reliability assurances as seen in large scale backend systems:

* High availability and resilience against errors
* Good test coverage and monitoring
* Information security

### Resilience Against Errors

All large scale backend systems that are dependent on other networked components encounter errors on a regular basis. However, the backend system itself must not fail catastrophically just because some of its dependent components have failed or returned errors. For example, thousands of hard disks in Google data centers fail daily; yet, Google as an overall service do not fail just because a thousand hard disks has failed on a Saturday.

Hummingbot and Hummingbot gateway have similar challenges, though at a smaller scale. Exchange APIs and blockchain transactions regularly fail, and blockchain transactions have their own unique modes of failures because of the different system architecture compared to the usual server-client architectures. The resilience requirements for Hummingbot and Hummingbot gateway, however, are the same - just because Ethereum is congested, or the mempool has dropped your transaction, the bot and the gateway must not fail in a catastrophic manner.

#### Nonce

Most blockchains, including Ethereum and all EVM based chains, enforce a sequential order of transactions. This is enforced by a unique nonce number for user transactions. In particular, every transaction signed by an Ethereum address must have a unique and monotonically increasing nonce number. The first transaction sent by an address must have a nonce of 0, the second transaction must have a nonce of 1, and so on.

It's possible for gateway clients to request EVM transactions faster than the blockchain network can acknowledge and process them. Thus, the gateway cannot depend on the last nonce reported from Ethereum node APIs for creating new transactions, or it'd risk overwriting recently sent transactions with duplicate nonce numbers.

In the original version of Hummingbot gateway, all transaction-emitting API calls would create new blockchain transactions; it was further assumed that the underlying blockchain would be able to process transactions so quickly, they appear to be "immediate" from the perspective of Hummingbot. Both of these assumptions are often not true in practical mainnet chains, where network congestion is the norm rather than the exception. The mismatched assumptions caused the original gateway to seem to pass testing on Ethereum test nets, or networks with fast block times - but fail on Ethereum main net.

Gateway v2 will come with the following architectural changes to account for how real-world Ethereum blockchains work:

* All transaction-emitting APIs will be made nonce-aware - such that unconfirmed or stuck blockchain transactions can be re-tried with higher gas fee or cancelled.

* In the case that Hummingbot or gateway clients are emitting batches transactions quickly - the gateway will track the newest nonce used locally, to make sure the new transactions will be emitted with increasing nonces rather than overwriting each other.

* The local nonce tracking manager will store the latest nonce in a fast local database, to ensure proper self-healing if gateway crashes and restarts.

#### Stuck and dropped transactions

Almost all blockchains today use the concept of transaction fees and mempool to prioritize transactions to include into new blocks. Since miners or validators are automatically incented to prioritize higher fee transactions, transactions marked with lower fees are often delayed or even dropped.

This causes additional problems when considering blockchain transactions must be executed serially. Let's say I've sent transactions with nonces 3, 4, 5 to Ethereum network. If transaction 3 is stuck, then transactions 4 and 5 cannot be processed before 3 has been processed. Thus, just having one transaction stuck or dropped by a blockchain can cause all subsequent transactions to be stuck or dropped.

This transaction semantic is very different from the usual semantic of server API calls. Gateway's job here, is to bridge the unreliable semantics of blockchain transactions to the usual reliable semantics of API calls - s.t. API clients can either hand off some of the processing complexity to gateway, or at least be informed and be able to respond to transaction events (including errors and getting stuck) in a timely manner.

Gateway v2 will be making the following changes to allow for cancelling or retrying stuck transactions:

* `/poll` API will carry additional response fields to account for transactions that don't yet exist in mempool, transactions that are stuck in mempool, in addition to confirmed transactions.
* A new `/cancel` API, which allows for cancelling stuck transactions.
* All transaction-emitting APIs, including /cancel, will accept `maxFeePerGas`, `maxPriorityFeePerGas`, and `nonce` arguments, to allow Hummingbot to retry stuck transactions with different gas costs.
* Also, as implied by the `maxPriorityFeePerGas` argument, we're adding support for EIP-1559 transactions.

#### Blockchain node errors

Blockchain node API calls (e.g. all ethers.js calls) can fail. The most common reason being network disruptions. The gateway should fail gracefully, rather than catastrophically, in the face of node API errors. It should also give informative errors in the logs, to give visibility to users either on Hummingbot side, or on the standalone gateway logs.

In the original Hummingbot gateway, errors from blockchain node API interactions would often produce cryptic error logs that are confusing to users. While the original Hummingbot gateway did catch for errors when performing blockchain operations, it didn't explicitly catch for common error classes like blockchain node errors and provide legible log message for those cases.

Gateway v2 will carry additional test coverage for blockchain node errors. It will also carry improved error logging for node error cases, to make sure users on Hummingbot side will receive legible and actionable error messages.

#### Node API rate limits

This is a more specific, but also common node errors case. Node services like Infura come with API rate limits - once exceeded, the gateway client would get temporarily banned. There are two major things we can do to reduce the number of API calls to blockchain node - reducing the number of calls, and monitoring.

The original Hummingbot gateway did not account for the node API rate limits from common services like Infura, and so exceeding API rate limits and getting banned became one of the most common errors in the original Hummingbot gateway.

Gateway v2 will carry the following architectural changes to reduce the number of API calls made to node services like Infura, and monitor the number of API calls made over time:

Caching logic for repeated blockchain information polls calls from Hummingbot, which is useful for saving node API calls before a new block has arrived.

Metrics for monitoring the amount of API calls made to blockchain nodes every 5 minutes, which will be useful for catching undetected API call hogs on Hummingbot side, or inside the gateway.

### Test Coverage and Monitoring

Test cases and monitoring metrics are the other side of the coin for any resilient and reliable software. In general, we can only improve the reliability of a piece of software, if we constantly measure the software's behavior in different cases via test cases and metrics.

While the original Hummingbot gateway carried some test cases - they were not useful for uncovering problems because almost all of them focused on only the happy cases. As a result, most of the error paths were not tested, and effective test coverage was poor.

In the following sections, we will discuss what needs to be tested, how the tests should be constructed, and what kind of monitoring to implement.

#### What to test

We cannot implement tests for absolutely every logic path, especially not at the beginning. So it's important to discuss what types of tests should be priority, and why.

* **Normal user flows:** These include testing all the logic paths used in normal operation of Hummingbot and gateway. This would include, but not limited to, testing for the normal flows for operations like getting the gas cost, getting asset prices, creating orders, getting transaction status, etc.
* **Common error flows:** These include testing the commonly encountered error paths in the normal operation of Hummingbot and gateway. These would include, but not limited to, network errors while making node API calls, transactions not being registered on the blockchain, not enough ETH for paying the gas cost, not enough balance for creating the orders, etc.
* **Regression testing:** Bug fixes, especially those concerning logic problems within the code (rather than, say, typographic mistakes) - should come with unit test cases to make sure they do not come back after further code changes. While this may seem like a hassle in early development, regression tests will save the engineering team a lot of time re-fixing bugs later on.

#### Test fixtures

It is difficult to test for common error flows unless we have a reliable way of reproducing or simulating them in test cases. There is no known reliable way to coax a blockchain to give us errors consistently - so simulation is the only way. This means some test fixtures for simulating various responses from the blockchain or blockchain related libraries (e.g. Uniswap order router) is required.

We will likely need to expand the test fixtures to testing success cases later as well - again, because blockchain operations are inherently unreliable - so there's also no known way to make it not give us errors.

We will start by constructing small set of prototype unit test cases, with the test fixtures that are able to simulate failure cases. Once we have that, we will be able to write more unit test cases based on the same fixture architecture.

#### Monitoring

It is not always enough to rely on user bug reports to gauge the stability of complicated backend systems. Passive monitoring metrics are often required for ensuring the quality of modern systems. Besides monitoring for reliability, metrics can also help us better understand how gateways are being used in the wild - which can help us better craft our product roadmap later on.

* **Unit test coverage monitoring:** Gateway v2 will target for a 30% to 40% unit test coverage during the early staging, and gradually move the test coverage to 60%+ as the project matures. This is a similar test coverage trajectory we used for the Hummingbot project.
* **Usage and error metrics of important logic flows:** These include counts of errors, error logs, or metrics that may lead to errors like the number of node API calls per 5 minutes discussed before. Gateway v2 will carry anonymous telemetry for usage and error metrics, s.t. Hummingbot team can be made aware of new errors in software releases even before users has reported a bug. Telemetry will only be enabled on Gateway v2 with user consent, and all the metrics data collected will be stored in an anonymized manner.

### Information Security

Since gateway API calls often carry the wallet private key in plaintext form, it is important to make sure gateway and gateway clients (including Hummingbot) authenticate each other before sending anything to the other side.

The original Hummingbot gateway already comes with SSL authentication for both sides, which already provides some protection against malicious software trying to intercept the private keys in transit. However, the mechanisms to protect the passphrase to the SSL private key is weak in the original Hummingbot gateway, and we are going to strengthen the security around the SSL private keys in Gateway v2.

Here are the changes Gateway v2 will carry on the information security side:

**Better protection for the SSL private key passphrase on Hummingbot side and gateway side**
  
* Hummingbot side: the passphrase will be encrypted with the Hummingbot password, as opposed to being a plaintext setting in one of the config files.
* Gateway side: the passphrase will be isolated in its own file, with `0600` UNIX permissions - rather than being mixed into other config files. This is similar to how SSL private key passphrases are usually protected in web servers.

**Eliminating the need to pass the wallet private key in gateway API calls**

* We are going to eventually migrate to using encrypted wallet files shared between Hummingbot and Gateway v2, instead of passing the wallet private key in API requests. This will come in a subsequent release after the initial public release of Gateway v2.
* Since encrypted wallet files still depend on passphrases, the passphrase security features outlined in point 1 above will still apply.

## User Experience

Hummingbot Gateway is a backend system, where the ideal user experience is it's easy to set up, and then it runs reliably in the background and let the user focus on trading. In the occasion the user needs to reconfigure or upgrade the gateway, the documentations and instructions should be clear, and the configuration steps should be easy to carry out.

Gateway v2 is going to come with a series of improvements to bring its user experience more in-line with major production server software like Apache or MySQL. We will be focusing our efforts in the following major areas:

* Setting up Gateway (using Hummingbot)
* Setting up Gateway (standalone)
* Configuring Gateway
* User Documentation

### Setting up Gateway (using Hummingbot)

The current Hummingbot / Gateway setup experience has a few usability issues:

1. Poor documentation: There are no coherent instructions on what the user needs to do to start trading on Uniswap.
2. Complexity: The user needs to set up the SSL certificates on Hummingbot first, and then either run another script (for Docker setup) or manually fill in the gateway configurations (for source setup) to get gateway working.
3. Little to no UX feedback: When gateway has been started, there is no UX feedback on Hummingbot to indicate it's been connected to a gateway.
4. None of the `gateway` commands come with `-h` help messages.

Here are the improvements we are going to add to Gateway v2, to make the Hummingbot setup workflow easier and more maintainable for users:

1. Automate the Gateway v2 Docker setup process within Hummingbot command line, instead of requiring the user to set up gateway outside of Hummingbot
2. Provision detailed, step-by-step documentations on the preparations steps, setup steps, and the configurations involved in gateway setup with Hummingbot to the Hummingbot documentation site
3. Add Gateway status to top status bar in the Hummingbot client UI, to indicate whether Hummingbot is connected to a Gateway v2 instance
4. Provision help messages for all `gateway` commands in Hummingbot

### Setting up Gateway (standalone)

There is currently no documented way of setting up Gateway in a standalone manner, and connecting non-Hummingbot clients to it. Since a standalone Gateway requires a non-Hummingbot client, we can expect most of the people needing this to be trading system developers and system administrators.

Here's the ideal user flow for someone developing a trading system with standalone a Gateway:

1. Developer reads an overview documentation on the overall architecture of Gateway, how to set it up, and how to connect non-Hummingbot clients to it
2. Developer sets up Gateway with `create-gateway.sh`, with the SSL certificates (including the CA certs and keys) generated
3. Developer generates a client cert from the CA certificates with `create-gateway-client-cert.sh`
4. Developer connects his custom client to Gateway with the client certificate, and completes his first "Hello world" Gateway API call (e.g. getting the price of ETH-DAI on Uniswap) from their client
5. Developer continues to develop their trading client by following our gateway API documentation

Here are the improvements we are going to add to Gateway v2, targeting the standalone gateway setup workflow:

1. Repurpose `create-gateway.sh` for standalone gateway setup. Since we cannot depend on Hummingbot on creating the SSL certificates, it should now create the SSL certificates, including the certificate authority
2. Add `create-gateway-client-cert.sh`, which generates client SSL keys and certificates, and signs the certs from the certificate authority generated from `create-gateway.sh`
3. Provision detailed, step-by-step documentations on the preparation steps, setup steps and the configurations involved in standalone gateway setup. Also, add a "Hello World" example for developers to start developing with Gateway API

### Configuring Gateway

The requirements for maintaining a user-friendly set of configurations for Hummingbot gateway is really not too different from that of a web server like Apache or NGINX, or that of a NodeJS web application. We should reference how configuration sets are maintained in those servers, rather than trying to re-invent the wheel.

Here are some ideal user flows for a few important scenarios w.r.t. configurations:

1. Hummingbot / Gateway setup: from Hummingbot, the user can simply set up their wallet, input their Infura key, and start the gateway
2. Standalone Gateway setup: the user runs a script to create the SSL certificates and have them integrated to the gateway configs automatically, inputs their Infura key, and starts the gateway
3. Inspecting configs from UNIX command line: the user can edit a few well-defined, and easy-to-read configuration files (e.g. `local.yml` for local settings like Infura key or node URL, `ssl.yml` for things like SSL certificate and key phrase file paths)
4. Inspecting configs from Hummingbot: the user can use `gateway list-configs` and `gateway update`
5. Adding or developing new connector module: the developer should be able to add his own module-specific configs in his own module's files, without needing to modify the global configs. However, module-specific configs should still be override-able in local settings files, and discoverable / writable from Hummingbot gateway commands.

We are going to refactor the configuration system of Gateway v2 by splitting the configuration files into multiple files, and bringing it more in-line with common server software like Apache and NGINX.

1. Keep the default settings for different connectors without their own module directories, to allow for modularity.
2. Remove global config file, use purpose-specific config files instead: `ssl.yml` for SSL certificate configurations, `ethereum.yml` for Ethereum chain-wide configurations (e.g. which network to use? Infura node ID?), and `local.yml` for user overrides.
3. Provide a directory with sample config files. (e.g. ./config/samples/), with in-line documentation of what each configuration entry means.

### User Documentation

The original Hummingbot Gateway came with installation instructions for Docker and source code installations, and discussed some `gateway` commands from Hummingbot without mentioning. However, there is no coherent explanation at when the user should apply which step, and why certain steps (e.g. SSL certificate generation) are needed.

It also does not describe the minimal set of configurations (e.g. Ethereum node URL, network, etc.) the user needs to have to get gateway working. This means a first-time user compiling from source code would need to resort to trial-and-error to get the gateway working. Overall, the current state of documentations for first-time users is unsatisfactory.

The installation documentation for Gateway v2 will be greatly expanded, and we will also make sure it's written in a sensible order and narrated in a coherent manner for first time users. In particular, the new installation documentations will give clear instructions on what are the preparation steps (e.g. OS environment with Docker, Ethereum node URL / Infura account, etc.) and the minimal set of configurations required to get Gateway v2 running.

## Developer Experience

Hummingbot is an open source project. We expect that in the long term, community members will be making the majority of contributions for DEX connectors, feature requests and bug fixes.

This implies we will also need to account for the user experience from the point of view of community developers. For example, consider somebody who wants to develop a new DEX connector for Hummingbot Gateway - we will need to plan for things like documentations, community support, the process of proposing and adding new connectors, the acceptance standards on our side, etc.

### Developer Documentation

Documentation is typically one of the first stops for developers looking to add new features to a project. We are expecting most developers will be interested in adding connectors to new DEXes to our project, so we will pay extra attention to writing and testing new connectors. Below is an outline of the kinds of developer documentations we are going to include with Gateway v2:

#### Quick start

This should be similar to the initial setup documentations in the User Experience workflows above, but with an emphasis of setting up gateway from source code rather than from Docker. It should include the following items:

* Preparations
  * OS and toolchain requirements. e.g. Linux / macOS, git, nvm, yarn, etc.
* Source code setup
  * Cloning from Hummingbot repository, yarnsetup steps, etc.
* Minimal configurations for Uniswap and Ethereum blockchain.
  * Generating the client SSL certificates for testing.
  * Editing configuration files for things like Infura API key.
* Verifying that the setup works
  * Provide a few curlcommands that make some Uniswap API requests (e.g. getting asset prices) to the gateway, and the expected output.

#### Code walkthrough with Uniswap connector

This will be a dedicated section for developers who are looking to develop new gateway connectors. The code walkthrough should capture the main logic pathways used in gateway, while running a Uniswap AMM strategy on Hummingbot.

#### Things to watch out and test for

It is relatively easy to write a DEX and blockchain connector that "mostly" works, "occasionally" works, or only works in a test net. The requirement for a new connector, however, is that it should be highly reliable and resilient against failures.

* Listing of common failure modes for DEX connectors. e.g. network disruption, stuck transactions, proper nonce management, etc.
* Listing of required unit test cases and fixtures against common error modes, in order for a connector to be certified by us.

#### API documentation

This includes documentations for every available API endpoint in Gateway v2, with argument inputs, expected output format, and errors.

### Feedback Loop

After reading through the documentations, community developers will need guidance from the moment they got the first "Hello World"-style API working, to the moment the new connector is approved and accepted by the Hummingbot team.

This feedback to the developer can come in many forms in addition to community feedback and discussions. Test cases, documentations and certification standards are also useful for the community developer to pace himself and make sure he's on the right track.

Gateway v2 will come with the following documentations and support infrastructure, to act as guardrails for community developers looking to create new connectors and new features for Gateway v2.

#### Instructions for running unit test cases

One of the first type of feedback a developer gets on his code, is typically from test cases. This can come in the form of unit test cases, or manual test cases (e.g. invoking `curl` with special instructions). Documentations that target the use and creation of test cases would be useful here.

In particular, we are going to provision the following test-related documentations with Gateway v2:

* How to run the unit test cases included in Gateway v2 code;
* How to write new unit test cases, and have it included in the test suite;
* How to run manual tests with curl, and generated client certificates.

#### Test fixtures to simulate common edge cases

We expect most of the new DEX connectors will be interfacing with EVM based blockchains - in which many of the same failure modes will apply. This means the test fixtures we constructed for testing Ethereum DEXes like Uniswap can likely be reused by our community developers.

Again, documentations on how to reuse and modify these test fixtures will be useful for community developers:

* Listing of common failure modes for DEX connectors. e.g. network disruption, stuck transactions, improper nonce management, etc.
* Documentations on the built-in test fixtures for testing EVM failure modes, and how they may be reused for testing new EVM based DEX connectors.

#### Process for submitting and certifying new connectors

The Hummingbot team will establish and publish a process, and a standard for certifying new DEX connectors. Any new DEX connectors must contain a required set of test cases to make sure it's reliable and resilient against common error cases. It should also pass through our code review and QA to ensure the test cases actually do what they claim to do, and that the connector actually works in our test environments.

#### Community channels
  
The Hummingbot team has established a Discord channel #dev-gateway-v2 dedicated to Hummingbot gateway community developers. From our experience with Hummingbot, the community channel will likely need support from the initial Gateway v2 dev team at the beginning. Eventually, once there are more community developers who have gone through the whole process, they will increasingly be able to support themselves.

After the initial public release of Gateway v2, we will establish a rotating "office hour" schedule, where members from the Gateway v2 dev team will answer questions from the community in the Gateway v2 community channel.

## Availability and Timeline

Hummingbot Gateway v2 is currently under active development under the branch [`feat/gateway-v2`](https://github.com/CoinAlpha/hummingbot/tree/feat/gateway-v2). Issues related to Gateway are tagged with the `gateway` label.

At the time this blog post is written, Gateway v2 is prototype, pre-alpha software, so our priority is to build a production-ready architecture that offers extensible support for Uniswap-style AMMs on EVM-compatible chains.

We are putting the architectural proposals detailed in this blog series into code as fast as possible. We expect the initial public release of Gateway v2 to be ready in Q1 2022, and we will start accepting pull requests from the community once the initial public release is ready.

In the meantime, we welcome feedback from the developer community. If you have any suggestions for Hummingbot Gateway v2, feel free to drop us a message in the **#dev-general** channel in our Discord server. For projects and exchanges seeking to integrate with Gateway, please contact us to get access to a private **#dev-gateway-v2** channel for technical support from our developers.