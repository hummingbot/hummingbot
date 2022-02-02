from decimal import Decimal

from sqlalchemy import BigInteger, TypeDecorator


class SqliteDecimal(TypeDecorator):
    """
    This TypeDecorator use Sqlalchemy BigInteger as impl. It converts Decimalsfrom Python to Integers which is later
    stored in Sqlite database.
    """
    impl = BigInteger

    def __init__(self, scale):
        """
        :param scale: number of digits to the right of the decimal point to consider when storing the value in the DB
        e.g. value = Column(SqliteDecimal(2)) means a value such as Decimal('12.34') will be converted to 1234
        """
        TypeDecorator.__init__(self)
        self.scale = scale
        self.multiplier_int = 10 ** self.scale

    @property
    def python_type(self):
        return Decimal

    def process_bind_param(self, value, dialect):
        return self._convert_decimal(value)

    def process_result_value(self, value, dialect):
        if value is not None:
            value = Decimal(value) / self.multiplier_int
        return value

    def process_literal_param(self, value, dialect):
        return str(self._convert_decimal(value))

    def _convert_decimal(self, value: Decimal) -> int:
        return int(Decimal(value) * self.multiplier_int) if value is not None else value
