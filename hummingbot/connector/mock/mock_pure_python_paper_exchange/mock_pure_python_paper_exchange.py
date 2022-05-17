from hummingbot.connector.mock.mock_paper_exchange.mock_paper_exchange import MockPaperExchange


class MockPurePythonPaperExchange(MockPaperExchange):

    @property
    def name(self) -> str:
        return "mock_pure_python_paper_exchange"
