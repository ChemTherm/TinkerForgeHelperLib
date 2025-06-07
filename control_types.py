from enum import IntEnum


class Controls:
    class Entries(IntEnum):
        hasInputs = 1
        hasOutputs = 2

    types = {
        "ExtOutput": Entries.hasOutputs,
        "ExtInputOutput": Entries.hasInputs + Entries.hasOutputs,
        "valve": Entries.hasOutputs,
        "easy_PI": Entries.hasOutputs,
        "direct_Heat": Entries.hasOutputs,
        "ExtInput": Entries.hasInputs,
        "pressure": Entries.hasInputs,
        "FlowMeter": Entries.hasInputs,
        "thermocouple": Entries.hasInputs,
        "analytic": Entries.hasInputs,
        "mfc": Entries.hasInputs + Entries.hasOutputs,
        "Modbus_Pump": 0,
        "Vorgabe": 0,
    }


