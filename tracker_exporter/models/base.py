import json
from abc import ABCMeta


class Base:
    """Base class for objects."""

    __metaclass__ = ABCMeta

    def __str__(self) -> str:
        return str(self.to_dict())

    def __repr__(self) -> str:
        return str(self)

    def __getitem__(self, item):
        return self.__dict__[item]

    @classmethod
    def de_json(cls, data) -> dict:
        """Deserialize object."""
        if not data:
            return None

        data = data.copy()
        return data

    def to_json(self) -> dict:
        """Serialize object to json."""
        return json.dumps(self.to_dict())

    def to_dict(self) -> dict:
        """Recursive serialize object."""
        null_cleaner = lambda value: "" if value is None else value  # pylint: disable=C3001

        def parse(val):
            if isinstance(val, list):
                return [parse(it) for it in val]
            if isinstance(val, dict):
                return {key: null_cleaner(parse(value)) for key, value in val.items() if not key.startswith("_")}
            return val

        data = self.__dict__.copy()
        return parse(data)
