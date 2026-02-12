import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..device import XDevice

_LOGGER = logging.getLogger(__name__)

from .base import PropConv


class AirConditionPowerConv(PropConv):
    
    def __init__(self, index: int = 1):
        self.index = index
        self.prefix = f"{index}-"
        super().__init__(f"{self.prefix}acp", "climate")
        
    def decode(self, device: "XDevice", payload: dict, value: bool):
        _LOGGER.debug('AC Power decode: %s = %s', self.attr, value)
        payload[self.attr] = value

    def encode(self, device: "XDevice", payload: dict, value: bool):
        _LOGGER.debug('AC Power encode: %s = %s', self.attr, value)
        super().encode(device, payload, bool(value))


class AirConditionModeConv(PropConv):

    
    def __init__(self, index: int = 1):
        self.index = index
        self.prefix = f"{index}-"
        super().__init__(f"{self.prefix}acm", "climate", parent=f"{self.prefix}acp")
        
    def decode(self, device: "XDevice", payload: dict, value: int):
        _LOGGER.debug('AC Mode decode: %s = %s', self.attr, value)
        mode_map = {
            1: "cool", 
            4: "fan_only", 
            8: "heat", 
        }
        payload[self.attr] = mode_map.get(value, "cool")

    def encode(self, device: "XDevice", payload: dict, value: str):
        _LOGGER.debug('AC Mode encode: %s = %s', self.attr, value)
        mode_map = {
            "cool": 1, 
            "fan_only": 4, 
            "heat": 8,  
        }
        super().encode(device, payload, mode_map.get(value, 1))


class AirConditionCurrentTempConv(PropConv):
    
    def __init__(self, index: int = 1):
        self.index = index
        self.prefix = f"{index}-"
        super().__init__(f"{self.prefix}act", "climate", parent=f"{self.prefix}acp")
        
    def decode(self, device: "XDevice", payload: dict, value: int):
        _LOGGER.debug('AC Current Temp decode: %s = %s', self.attr, value)
        if 16 <= value <= 32:
            payload[self.attr] = value


class AirConditionTargetTempConv(PropConv):
    
    def __init__(self, index: int = 1):
        self.index = index
        self.prefix = f"{index}-"
        super().__init__(f"{self.prefix}actt", "climate", parent=f"{self.prefix}acp")
        
    def decode(self, device: "XDevice", payload: dict, value: int):
        _LOGGER.debug('AC Target Temp decode: %s = %s', self.attr, value)
        if 16 <= value <= 32:
            payload[self.attr] = value

    def encode(self, device: "XDevice", payload: dict, value: float):
        _LOGGER.debug('AC Target Temp encode: %s = %s', self.attr, value)
        temp = int(value)
        if temp < 16:
            temp = 16
        elif temp > 32:
            temp = 32
        super().encode(device, payload, temp)


class AirConditionFanSpeedConv(PropConv):
    
    def __init__(self, index: int = 1):
        self.index = index
        self.prefix = f"{index}-"
        super().__init__(f"{self.prefix}acf", "climate", parent=f"{self.prefix}acp")
        
    def decode(self, device: "XDevice", payload: dict, value: int):
        _LOGGER.debug('AC Fan Speed decode: %s = %s', self.attr, value)
        speed_map = {
            1: "high",
            2: "medium", 
            4: "low",
        }
        payload[self.attr] = speed_map.get(value, "medium")

    def encode(self, device: "XDevice", payload: dict, value: str):
        _LOGGER.debug('AC Fan Speed encode: %s = %s', self.attr, value)
        speed_map = {
            "high": 1,
            "medium": 2,
            "low": 4,
        }
        super().encode(device, payload, speed_map.get(value, 2))

class AirConditionCurrentTempSensorAcctConv(PropConv):
    def __init__(self, index: int = 1):
        self.index = index
        self.prefix = f"{index}-"
        super().__init__(f"temperature{index}", "sensor", prop=f"{self.prefix}acct")

    def decode(self, device: "XDevice", payload: dict, value: int):
        _LOGGER.debug('AC Sensor Acct Temp decode: %s = %s', self.attr, value)
        if isinstance(value, (int, float)):
            payload[self.attr] = int(value)