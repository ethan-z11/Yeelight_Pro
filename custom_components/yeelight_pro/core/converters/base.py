from dataclasses import dataclass
from typing import Any, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..device import XDevice

__all__ = [
    'Converter', 'BoolConv', 'MapConv', 'DurationConv',
    'PropConv', 'PropBoolConv', 'PropMapConv',
    'BrightnessConv', 'ColorTempKelvin', 'ColorRgbConv',
    'EventConv', 'MotorConv', 'CoverPositionConv', 'CoverStateConv',
    'TiltAngleConv', 'SceneConv',
    'BathHeaterModeConv',
]


@dataclass
class Converter:
    attr: str  # hass attribute
    domain: Optional[str] = None 

    prop: Optional[str] = None
    parent: Optional[str] = None

    enabled: Optional[bool] = True  
    poll: bool = False  

    childs = None 

    def decode(self, device: "XDevice", payload: dict, value: Any):
        payload[self.attr] = value

    def encode(self, device: "XDevice", payload: dict, value: Any):
        payload[self.prop or self.attr] = value

    def read(self, device: "XDevice", payload: dict):
        if not self.prop:
            return


class BoolConv(Converter):
    def decode(self, device: "XDevice", payload: dict, value: Union[bool, int]):
        payload[self.attr] = bool(value)

    def encode(self, device: "XDevice", payload: dict, value: Union[bool, int]):
        super().encode(device, payload, bool(value))


@dataclass
class MapConv(Converter):
    map: dict = None

    def decode(self, device: "XDevice", payload: dict, value: Union[str, int]):
        payload[self.attr] = self.map.get(value)

    def encode(self, device: "XDevice", payload: dict, value: Any):
        value = next(k for k, v in self.map.items() if v == value)
        super().encode(device, payload, value)


@dataclass
class DurationConv(Converter):
    min: float = 0
    max: float = 3600
    step: float = 1
    readable: bool = True

    def decode(self, device: "XDevice", payload: dict, value: Union[int, float, str, None]):
        if self.readable and value is not None:
            payload[self.attr] = int(float(value) / 1000)

    def encode(self, device: "XDevice", payload: dict, value: Union[int, float, str, None]):
        if value is not None:
            super().encode(device, payload, int(float(value) * 1000))


class PropConv(Converter):
    pass


class PropBoolConv(BoolConv, PropConv):
    pass


class PropMapConv(MapConv, PropConv):
    pass


@dataclass
class BrightnessConv(PropConv):
    max: float = 100.0

    def decode(self, device: "XDevice", payload: dict, value: int):
        payload[self.attr] = round(value / self.max * 255.0)

    def encode(self, device: "XDevice", payload: dict, value: float):
        value = round(value / 255.0 * self.max)
        super().encode(device, payload, int(value))


@dataclass
class ColorTempKelvin(PropConv):
    # 2700..6500 => 370..153
    mink: int = 2700
    maxk: int = 6500

    def decode(self, device: "XDevice", payload: dict, value: int):
        """Convert degrees kelvin to mired shift."""
        payload[self.attr] = int(1000000.0 / value)
        payload['color_temp_kelvin'] = value

    def encode(self, device: "XDevice", payload: dict, value: int):
        value = int(1000000.0 / value)
        if value < self.mink:
            value = self.mink
        if value > self.maxk:
            value = self.maxk
        super().encode(device, payload, value)


class ColorRgbConv(PropConv):
    def decode(self, device: "XDevice", payload: dict, value: int):
        red = (value >> 16) & 0xFF
        green = (value >> 8) & 0xFF
        blue = value & 0xFF
        payload[self.attr] = (red, green, blue)

    def encode(self, device: "XDevice", payload: dict, value: tuple):
        value = (value[0] << 16) | (value[1] << 8) | value[2]
        super().encode(device, payload, value)


@dataclass
class EventConv(Converter):
    event: str = ''

    def decode(self, device: "XDevice", payload: dict, value: dict):
        key, val = self.attr, None
        if '.' in self.attr:
            key, val = self.attr.split('.', 1)
        if key in ['motion', 'contact', 'approach']:
            payload.update({
                key: val in ['true', 'open', 'start'],
                **value,
            })
        elif self.attr in ['panel.click', 'panel.hold', 'panel.release', 'keyClick']:
            key = value.get('key', '')
            cnt = value.get('count', None)
            btn = f'button{key}'
            if cnt is not None:
                typ = {1: 'single', 2: 'double', 3: 'triple'}.get(cnt, val)
            else:
                typ = val
            if typ:
                btn += f'_{typ}'
            payload.update({
                'action': btn,
                'event': self.attr,
                'button': key,
                **value,
            })
        elif self.attr in ['knob.spin']:
            keys = ['free_spin', 'hold_spin']
            keys += [ f"{i}-free_spin" for i in range(1,5)] # For E-Series Knob Support
            for typ in keys:
                if value.get(typ) in [None, 0]:
                    continue
                payload.update({
                    'action': typ,
                    'event': self.attr,
                    **value,
                })

    def encode(self, device: "XDevice", payload: dict, value: dict):
        super().encode(device, payload, value)


@dataclass
class MotorConv(Converter):
    readable: bool = False

    def decode(self, device: "XDevice", payload: dict, value: Any):
        """解码窗帘电机状态"""
        if isinstance(value, dict):
            # 处理运行状态
            if 'run_state' in value:
                state = value['run_state']
                if state == 1:
                    payload['run_state'] = 'opening'
                elif state == 2:
                    payload['run_state'] = 'closing'
                elif state == 0:
                    payload['run_state'] = 'closed'
            
            # 处理位置信息
            if 'tp' in value:  # target position
                payload['position'] = value['tp']
            if 'cp' in value:  # current position
                payload['current_position'] = value['cp']
        elif self.readable and value is not None:
            payload[self.attr] = value

    def encode(self, device: "XDevice", payload: dict, value: Any):
        """编码窗帘控制命令"""
        if value == 'stop':
            # 暂停命令（协议：action.motorAdjust.type = "pause"）
            payload['action'] = {'motorAdjust': {'type': 'pause'}}
        elif isinstance(value, int):
            # 设置位置命令
            super().encode(device, payload, {
                'tp': value,  # target position
            })


@dataclass  
class CoverPositionConv(PropConv):
    """窗帘位置转换器"""
    min: int = 0
    max: int = 100

    def decode(self, device: "XDevice", payload: dict, value: int):
        payload[self.attr] = value

    def encode(self, device: "XDevice", payload: dict, value: int):
        # 确保位置在有效范围内
        if value < self.min:
            value = self.min
        elif value > self.max:
            value = self.max
        super().encode(device, payload, value)


@dataclass
class CoverStateConv(PropConv):
    """窗帘状态转换器"""


class BathHeaterModeConv(PropConv):
    def __init__(self):
        super().__init__('heater_mode', 'select', prop='bhm', parent='heater_power')
        self.map = {
            0: '关闭',
            1: '智能干燥',
            2: '恒温除雾',
            3: '快速除雾',
            4: '极速加热',
        }
        self.childs = set()
        self.option = {'name': '快速模式'}

    def decode(self, device: "XDevice", payload: dict, value: int):
        payload[self.attr] = self.map.get(value, '关闭')

    def encode(self, device: "XDevice", payload: dict, value: str):
        rev = {v: k for k, v in self.map.items()}
        code = rev.get(value, 0)
        if code == 0:
            payload['p'] = False
        else:
            payload['p'] = True
            payload['bhm'] = code
    


@dataclass
class TiltAngleConv(PropConv):
    min: int = 0
    max: int = 180

    def decode(self, device: "XDevice", payload: dict, value: int):
        payload[self.attr] = int(value)

    def encode(self, device: "XDevice", payload: dict, value: int):
        if value is None:
            return
        if value < self.min:
            value = self.min
        elif value > self.max:
            value = self.max
        super().encode(device, payload, int(value))


@dataclass
class SceneConv(Converter):
    node: dict = None


from .climate import (
    AirConditionPowerConv,
    AirConditionModeConv, 
    AirConditionCurrentTempConv,
    AirConditionTargetTempConv,
    AirConditionFanSpeedConv,
)