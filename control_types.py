from enum import IntEnum


class Controls:
    class Entries(IntEnum):
        hasInputs = 1
        hasOutputs = 2

    types = {
        "ExtOutput": Entries.hasOutputs,
        "valve": Entries.hasOutputs,
        "easy_PI": Entries.hasOutputs,
        "ExtInput": Entries.hasInputs,
        "pressure": Entries.hasInputs,
        "thermocouple": Entries.hasInputs,
        "mfc": Entries.hasInputs + Entries.hasOutputs,
    }


