UNIT_MULTIPLIER = 1e18
TEST_ADDRESS = 'TEST_ADDRESS'
TEST_PASSWORD = 'TEST_PASSWORD'


outputs = {
    # For order_amount of 1
    ('celocli', 'exchange:show', '--amount', str(int(9.95 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(9.95 * UNIT_MULTIPLIER))} CELO => {str(int(99.5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(9.95 * UNIT_MULTIPLIER))} cUSD => {str(int(1 * UNIT_MULTIPLIER))} CELO",

    ('celocli', 'exchange:show', '--amount', str(int(1 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(1 * UNIT_MULTIPLIER))} CELO => {str(int(10.5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(1 * UNIT_MULTIPLIER))} cUSD => {str(int(0.095 * UNIT_MULTIPLIER))} CELO",

    # For order_amount of 2
    ('celocli', 'exchange:show', '--amount', str(int(9.9 * 2 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(9.9 * 2 * UNIT_MULTIPLIER))} CELO => {str(int(99.5 * 2 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(9.9 * 2 * UNIT_MULTIPLIER))} cUSD => {str(int(1.05 * 2 * UNIT_MULTIPLIER))} CELO",

    ('celocli', 'exchange:show', '--amount', str(int(2 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(2 * UNIT_MULTIPLIER))} CELO => {str(int(10 * 2 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(2 * UNIT_MULTIPLIER))} cUSD => {str(int(0.095 * 2 * UNIT_MULTIPLIER))} CELO",


    ('celocli', 'exchange:show', '--amount', str(int(9.83 * 5 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(9.83 * 5 * UNIT_MULTIPLIER))} CELO => {str(int(99.5 * 5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(9.83 * 5 * UNIT_MULTIPLIER))} cUSD => {str(int(0.99 * 5 * UNIT_MULTIPLIER))} CELO",

    ('celocli', 'exchange:show', '--amount', str(int(5 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(5 * UNIT_MULTIPLIER))} CELO => {str(int(10.1 * 5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(5 * UNIT_MULTIPLIER))} cUSD => {str(int(0.095 * 5 * UNIT_MULTIPLIER))} CELO",

    ('celocli', 'account:unlock', TEST_ADDRESS, '--password', TEST_PASSWORD):
        "",

    ('celocli', 'account:balance', TEST_ADDRESS):
        "All balances expressed in units of 10^-18.\n"
        "CELO: 9007508147186651319\n"
        "lockedCELO: 0\n"
        "cUSD: 29630453216355095281\n"
        "pending: 0",

    ('celocli', 'exchange:gold', '--from', TEST_ADDRESS, '--value', str(int(1 * UNIT_MULTIPLIER)),
     '--forAtLeast', '10489500000000000000'):
        "Sending Transaction: increaseAllowance... done\n"
        "SendTransaction: increaseAllowance\n"
        "txHash: 0xfd0777b214f4993c8f182e3d90ce15cee9db59aa0ec48621c68dadc880316c0e\n"
        "Sending Transaction: exchange... done\n"
        "SendTransaction: exchange\n"
        "txHash: 0xTEST_TX_HASSHHHHHHHHHHH\n",

    ('celocli', 'exchange:dollars', '--from', TEST_ADDRESS, '--value', str(int(1 * UNIT_MULTIPLIER))):
        "SendTransaction: increaseAllowance\n"
        "txHash: 0xc01bdc3a8059a26519db0448d05fbf585cc63bb1a762e0da1b94f2a118ca4035\n"
        "Sending Transaction: increaseAllowance... done\n"
        "SendTransaction: exchange\n"
        "txHash: 0xTEST_TX_HASSHHHHHHHHHHH\n"
        "Sending Transaction: exchange... done",

    ('celocli', 'exchange:dollars', '--from', TEST_ADDRESS, '--value', '18857142857142857142',
     '--forAtLeast', '1998000000000000000'):
        "SendTransaction: increaseAllowance\n"
        "txHash: 0xc01bdc3a8059a26519db0448d05fbf585cc63bb1a762e0da1b94f2a118ca4035\n"
        "Sending Transaction: increaseAllowance... done\n"
        "SendTransaction: exchange\n"
        "txHash: 0xTEST_TX_HASSHHHHHHHHHHH\n"
        "Sending Transaction: exchange... done",

    ('celocli', 'node:synced'):
        "true",
}
