outputs = {
    ('celocli', 'exchange:show', '--amount', str(int(9.95 * 10e18))):
        "Fetching exchange rates...... done\n"
        f"{str(int(9.95 * 10e18))} cGLD => {str(int(99.5 * 10e18))} cUSD\n"
        f"{str(int(9.95 * 10e18))} cUSD => {str(int(1 * 10e18))} cGLD",

    ('celocli', 'exchange:show', '--amount', str(int(1 * 10e18))):
        "Fetching exchange rates...... done\n"
        f"{str(int(1 * 10e18))} cGLD => {str(int(10.1 * 10e18))} cUSD\n"
        f"{str(int(1 * 10e18))} cUSD => {str(int(0.095 * 10e18))} cGLD",

    ('celocli', 'exchange:show', '--amount', str(int(9.83 * 5 * 10e18))):
        "Fetching exchange rates...... done\n"
        f"{str(int(9.83 * 5 * 10e18))} cGLD => {str(int(99.5 * 5 * 10e18))} cUSD\n"
        f"{str(int(9.83 * 5 * 10e18))} cUSD => {str(int(0.99 * 5 * 10e18))} cGLD",

    ('celocli', 'exchange:show', '--amount', str(int(5 * 10e18))):
        "Fetching exchange rates...... done\n"
        f"{str(int(5 * 10e18))} cGLD => {str(int(10.1 * 5 * 10e18))} cUSD\n"
        f"{str(int(5 * 10e18))} cUSD => {str(int(0.095 * 5 * 10e18))} cGLD"
}
