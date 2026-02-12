import asyncio
import logging
from enum import IntEnum
from .converters.base import *
from .converters.base import TiltAngleConv

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .. import XEntity
    from .gateway import ProGateway
    from homeassistant.core import HomeAssistant

from homeassistant.components.light import ColorMode
from homeassistant.const import UnitOfTemperature

_LOGGER = logging.getLogger(__name__)


class NodeType(IntEnum):
    GATEWAY = -1
    ROOM = 1
    MESH = 2
    GROUP = 3
    MRSH_GROUP = 4
    HOME = 5
    SCENE = 6


class DeviceType(IntEnum):
    LIGHT = 1
    LIGHT_WITH_BRIGHTNESS = 2
    LIGHT_WITH_COLOR_TEMP = 3
    LIGHT_WITH_COLOR = 4
    CURTAIN = 6
    RELAY_DOUBLE = 7
    VRF = 10
    SWITCH_PANEL = 13
    LIGHT_WITH_ZOOM_CT = 14
    AIR_CONDITIONER = 15
    SIMPLE_SWITCH = 18    
    SWITCH_SENSOR = 128
    MOTION_SENSOR = 129
    MAGNET_SENSOR = 130
    KNOB = 132
    MOTION_WITH_LIGHT = 134
    ILLUMINATION_SENSOR = 135
    TEMPERATURE_HUMIDITY = 136
    BATH_HEATER = 2049
    AUDIO_DEVICE = 30


DEVICE_TYPE_LIGHTS = [
    DeviceType.LIGHT,
    DeviceType.LIGHT_WITH_BRIGHTNESS,
    DeviceType.LIGHT_WITH_COLOR_TEMP,
    DeviceType.LIGHT_WITH_COLOR,
    DeviceType.LIGHT_WITH_ZOOM_CT,
]


class XDevice:
    hass: "HomeAssistant" = None
    converters: Dict[str, Converter] = None

    def __init__(self, node: dict):
        self.id = int(node['id'])
        self.nt = node.get('nt', 0)
        self.pid = node.get('pid')
        self.type = node.get('type', node.get('pt', 0))
        self.pt = node.get('pt')
        self.name = node.get('n', '')
        self.prop = {}
        self.entities: Dict[str, "XEntity"] = {}
        self.gateways: List["ProGateway"] = []
        self.converters = {}
        self.setup_converters()

    def setup_converters(self):
        pass

    def add_converter(self, conv: Converter):
        self.converters[conv.attr] = conv

    def add_converters(self, *args: Converter):
        for conv in args:
            self.add_converter(conv)

    @staticmethod
    async def from_node(gateway: "ProGateway", node: dict):
        if node.get('nt') not in [NodeType.MESH, NodeType.MRSH_GROUP, NodeType.SCENE]:
            return None
        if not (nid := node.get('id')):
            return None
        if dvc := gateway.devices.get(nid):
            if n := node.get('n'):
                dvc.name = n
        else:
            dvc = XDevice(node)
            if dvc.nt in [NodeType.SCENE]:
                if isinstance(gateway.device, GatewayDevice):
                    await gateway.device.add_scene(node)
                return gateway.device
            elif dvc.type in DEVICE_TYPE_LIGHTS:
                dvc = LightDevice(node)
            elif dvc.type in [DeviceType.SWITCH_PANEL]:
                dvc = SwitchPanelDevice(node)
            elif dvc.type in [DeviceType.RELAY_DOUBLE]:
                dvc = RelayDoubleDevice(node)
            elif dvc.type in [DeviceType.SWITCH_SENSOR]:
                dvc = KnobDevice(node)                  
            elif dvc.type in [DeviceType.KNOB]:
                dvc = KnobDevice(node)
            elif dvc.type in [DeviceType.MOTION_SENSOR, DeviceType.MOTION_WITH_LIGHT]:
                dvc = MotionDevice(node)
            elif dvc.type in [DeviceType.MAGNET_SENSOR]:
                dvc = ContactDevice(node)
            elif dvc.type in [DeviceType.CURTAIN]:
                dvc = CoverDevice(node)
            elif dvc.type in [DeviceType.BATH_HEATER]:
                dvc = BathHeaterDevice(node)
            elif dvc.type in [DeviceType.VRF, DeviceType.AIR_CONDITIONER]:
                dvc = AirConditionDevice(node)
            elif dvc.type in [DeviceType.SIMPLE_SWITCH, 18]:
                dvc = SimpleSwitchDevice(node)               
            elif dvc.type in [DeviceType.AUDIO_DEVICE, 30]:
                dvc = AudioDevice(node)
            else:
                _LOGGER.warning('Unsupported device: %s', node)
                return None
            await gateway.add_device(dvc)
            await gateway.get_node(dvc.id, wait_result=True)
        return dvc

    @staticmethod
    async def from_nodes(gateway: "ProGateway", nodes: List[dict]):
        dls = []
        for node in nodes:
            if (dvc := XDevice.from_node(gateway, node)) is None:
                continue
            dls.append(dvc)
        return dls

    async def prop_changed(self, data: dict):
        has_new = False
        if 'params' in data:
            oldp = self.prop_params
            for k in (data.get('params') or {}).keys():
                if k not in oldp:
                    has_new = True
                    break
        else:
            for k in data.keys():
                if k not in self.prop:
                    has_new = True
                    break
        self.prop.update(data)
        if has_new:
            self.setup_converters()
            await self.setup_entities()
            for ent in self.entities.values():
                conv = self.converters.get(ent._name)
                if conv:
                    ent.subscribed_attrs = self.subscribe_attrs(conv)
        self.update(self.decode(data))

    async def event_fired(self, data: dict):
        decoded = self.decode_event(data)
        self.update(decoded)
        _LOGGER.debug('Event fired: %s', [data, decoded])

    @property
    def gateway(self):
        if self.gateways:
            return self.gateways[0]
        return None

    @property
    def online(self):
        return self.prop.get('o')

    @property
    def firmware_version(self):
        return self.prop.get('fv')

    @property
    def prop_params(self):
        return self.prop.get('params') or {}

    @property
    def unique_id(self):
        return f'{self.type}_{self.id}'

    def entity_id(self, conv: Converter):
        return f'{conv.domain}.yp{self.unique_id}_{conv.attr}'

    async def setup_entities(self):
        if not (gateway := self.gateway):
            return
        if not self.converters:
            _LOGGER.warning('Device has none converters: %s', [type(self), self.id])
        for conv in list(self.converters.values()):
            domain = conv.domain
            if domain is None:
                continue
            if conv.attr in self.entities:
                continue
            await asyncio.sleep(0.05)
            await gateway.setup_entity(domain, self, conv)

    def subscribe_attrs(self, conv: Converter):
        attrs = {conv.attr}
        if conv.childs:
            attrs |= set(conv.childs)
        attrs.update(c.attr for c in self.converters.values() if c.parent == conv.attr)
        return attrs

    def decode(self, value: dict) -> dict:
        payload = {}
        for conv in self.converters.values():
            prop = conv.prop or conv.attr
            data = value
            if isinstance(conv, PropConv):
                data = value.get('params') or {}
            if prop not in data:
                continue
            conv.decode(self, payload, data[prop])
        return payload

    def decode_event(self, data: dict) -> dict:
        payload = {}
        event = data.get('value') or data.get('type')
        if conv := self.converters.get(event):
            value = data.get('params') or {}
            conv.decode(self, payload, value)
        return payload

    def encode(self, value: dict) -> dict:
        payload = {}
        for conv in self.converters.values():
            if conv.attr not in value:
                continue
            if isinstance(conv, PropConv):
                dat = payload.setdefault('set', {})
            else:
                dat = payload
            conv.encode(self, dat, value[conv.attr])
        return payload

    def encode_read(self, attrs: set) -> dict:
        payload = {}
        for conv in self.converters.values():
            if conv.attr not in attrs:
                continue
            conv.read(self, payload)
        return payload

    def update(self, value: dict):
        if not value:
            return
        attrs = value.keys()

        for entity in self.entities.values():
            if not (entity.subscribed_attrs & attrs):
                continue
            entity.async_set_state(value)
            if entity.added:
                entity.async_write_ha_state()

    async def get_node(self):
        if not self.gateway:
            return None
        return await self.gateway.send('gateway_get.node', params={'id': self.id})

    async def set_prop(self, **kwargs):
        if not self.gateway:
            return None
        cmd = kwargs.pop('method', 'gateway_set.prop')
        node = {
            'id': self.id,
            'nt': self.nt,
            **kwargs,
        }
        return await self.gateway.send(cmd, nodes=[node])


class GatewayDevice(XDevice):
    def __init__(self, gateway: "ProGateway"):
        super().__init__({
            'id': 0,
            'nt': NodeType.GATEWAY,
            'pid': 'gateway',
            'type': 'gateway',
        })
        self.id = gateway.host
        self.name = 'Yeelight Pro'

    async def add_scene(self, node: dict):
        if not (nid := node.get('id')):
            return
        self.add_converter(SceneConv(f'scene_{nid}', 'button', node=node))
        await self.setup_entities()

    def entity_id(self, conv: Converter):
        return f'{conv.domain}.yp_{conv.attr}'


class LightDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converter(PropBoolConv('light', 'light', prop='p'))
        self.add_converter(DurationConv('delay', parent='light'))
        self.add_converter(DurationConv('delayoff', 'number', readable=False))
        self.add_converter(DurationConv('transition', prop='duration', parent='light'))
        if ColorMode.BRIGHTNESS in self.color_modes:
            self.add_converter(BrightnessConv('brightness', prop='l', parent='light'))
        if ColorMode.COLOR_TEMP in self.color_modes:
            self.add_converter(ColorTempKelvin('color_temp', prop='ct', parent='light'))
        if ColorMode.RGB in self.color_modes:
            self.add_converter(ColorRgbConv('rgb_color', prop='c', parent='light'))
        if self.type == DeviceType.LIGHT_WITH_ZOOM_CT:
            self.add_converter(PropConv('angel', 'number'))

    @property
    def color_modes(self):
        modes = {
            ColorMode.ONOFF,
        }
        if self.type == DeviceType.LIGHT_WITH_BRIGHTNESS:
            modes.add(ColorMode.BRIGHTNESS)
        if self.type == DeviceType.LIGHT_WITH_COLOR_TEMP:
            modes.add(ColorMode.BRIGHTNESS)
            modes.add(ColorMode.COLOR_TEMP)
        if self.type == DeviceType.LIGHT_WITH_COLOR:
            modes.add(ColorMode.BRIGHTNESS)
            modes.add(ColorMode.COLOR_TEMP)
            modes.add(ColorMode.RGB)
        return modes


class ActionDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converter(Converter('action', 'sensor'))


class SwitchSensorDevice(ActionDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converters(
            EventConv('panel.click'),
            EventConv('panel.hold'),
            EventConv('panel.release'),
        )


class RelayDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        switches = self.switches
        if len(switches) == 1:
            self.add_converter(PropBoolConv('switch', 'switch', prop='1-p'))
        else:
            for i, p in self.switches.items():
                self.add_converter(PropBoolConv(f'switch{i}', 'switch', prop=f'{i}-p'))

    @property
    def switches(self):
        lst = {}
        for i in range(1, 9):
            if (p := self.switch_power(i)) is None:
                continue
            lst[i] = p
        return lst

    def switch_power(self, index=1):
        return self.prop_params.get(f'{index}-p')


class SwitchPanelDevice(RelayDevice, SwitchSensorDevice):
    def setup_converters(self):
        super().setup_converters()
        SwitchSensorDevice.setup_converters(self)

        switches = self.switches
        if len(switches) == 1:
            self.add_converter(PropBoolConv('switch', 'switch', prop='1-sp'))
        else:
            for i, p in self.switches.items():
                self.add_converter(PropBoolConv(f'switch{i}', 'switch', prop=f'{i}-sp'))
        if '0-blp' in self.prop_params:
            self.add_converter(PropBoolConv('backlight', 'light', prop='0-blp'))

    def switch_power(self, index=1):
        return self.prop_params.get(f'{index}-sp')


class RelayDoubleDevice(XDevice):
    def setup_converters(self):
        self.add_converters(
            PropBoolConv('switch1', 'switch', prop='1-p'),
            PropBoolConv('switch2', 'switch', prop='2-p')
        )


class KnobDevice(SwitchSensorDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converter(EventConv('knob.spin'))


class MotionDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        params = self.prop_params
        self.add_converter(Converter('motion', 'binary_sensor'))
        if 'mv' in params:
            self.add_converter(PropBoolConv('motion', 'binary_sensor', prop='mv'))

        if 'approach' in params:
            self.add_converter(PropBoolConv('approach', 'binary_sensor', prop='approach'))

        self.add_converter(EventConv('motion.true'))
        self.add_converter(EventConv('motion.false'))
        self.add_converter(EventConv('approach.true'))
        self.add_converter(EventConv('approach.false'))

        if 'luminance' in params:
            self.add_converter(PropConv('luminance', 'sensor', prop='luminance'))
            self.converters['luminance'].option = {
                'name': '当前光照值',
                'class': 'illuminance',
                'unit': 'lx',
            }


class ContactDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converter(Converter('contact', 'binary_sensor'))
        self.add_converter(EventConv('contact.open'))
        self.add_converter(EventConv('contact.close'))


class CoverDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        _LOGGER.debug("Setting up cover device converters for device: %s", self.id)
        
        self.add_converters(
            MotorConv('motor', 'cover'),
            CoverPositionConv('position', parent='motor', prop='tp'),
            CoverPositionConv('current_position', parent='motor', prop='cp'),
            PropBoolConv('route_calibrated', None, prop='rs', parent='motor'),
        )
        self.converters['motor'].option = {'name': self.name}
        if (getattr(self, 'pt', None) == 22) or any(k in self.prop_params for k in ('cra', 'tra', 'trs')):
            self.add_converters(
                TiltAngleConv('current_angle', parent='motor', prop='cra'),
                TiltAngleConv('target_angle', None, prop='tra', parent='motor'),
                PropBoolConv('tilt_route_calibrated', None, prop='trs', parent='motor'),
            )
        
        if 'reverse' in self.prop_params:
            self.add_converter(PropBoolConv('reverse', 'switch', prop='reverse'))


class WifiPanelDevice(RelayDoubleDevice):
    def __init__(self, node: dict):
        super().__init__({
            **node,
            'type': 'wifi_panel',
        })
        self.name = 'Yeelight Wifi Panel'

    async def set_prop(self, **kwargs):
        kwargs['method'] = 'device_set.prop'
        return await super().set_prop(**kwargs)

    def entity_id(self, conv: Converter):
        return f'{conv.domain}.yp_{self.id}_{conv.attr}'

    def setup_converters(self):
        super().setup_converters()
        self.add_converter(Converter('action', 'sensor'))
        self.add_converter(EventConv('keyClick'))



class AirConditionDevice(XDevice):
    
    def setup_converters(self):
        super().setup_converters()
        
        from .converters.climate import (
            AirConditionPowerConv,
            AirConditionModeConv, 
            AirConditionCurrentTempConv,
            AirConditionTargetTempConv,
            AirConditionFanSpeedConv,
            AirConditionCurrentTempSensorAcctConv,
        )
        
        channels = self.detect_air_condition_channels()
        
        for i in range(1, channels + 1):
            self.add_converters(
                AirConditionPowerConv(i),
                AirConditionModeConv(i),
                AirConditionCurrentTempConv(i),
                AirConditionTargetTempConv(i),
                AirConditionFanSpeedConv(i),
            )

            params = self.prop_params
            if f"{i}-acct" in params:
                self.add_converter(
                    AirConditionCurrentTempSensorAcctConv(i)
                )
                self.converters[f'temperature{i}'].option = {
                    'name': f'{self.name} 室内温度',
                    'class': 'temperature',
                    'unit': UnitOfTemperature.CELSIUS,
                }
    
    def detect_air_condition_channels(self):
        channels = 1
        params = self.prop_params
        
        for key in params.keys():
            if key.startswith('2-') and 'acp' in key:
                channels = 2
                break
            if key.startswith('3-') and 'acp' in key:
                channels = 3
                break
                
        return channels
    
    async def setup_entities(self):
        if not (gateway := self.gateway):
            return
            
        channels = self.detect_air_condition_channels()
        
        for i in range(1, channels + 1):
            prefix = f"{i}-"
            conv_key = f"{prefix}acp"  
            
            if conv_key in self.converters and conv_key not in self.entities:
                conv = self.converters[conv_key]
                await asyncio.sleep(1)  
                await gateway.setup_entity("climate", self, conv)

        for conv in list(self.converters.values()):
            if conv.domain == 'sensor' and conv.attr not in self.entities:
                await asyncio.sleep(1)
                await gateway.setup_entity('sensor', self, conv)

class BathHeaterDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converter(PropBoolConv('heater_power', 'switch', prop='p'))
        self.converters['heater_power'].option = {
            'name': f'{self.name} 浴霸电源',
        }

        self.add_converter(BathHeaterModeConv())
        self.add_converter(PropConv('ventilation', 'fan', prop='ve'))
        self.add_converter(PropConv('blow', 'fan', prop='fa'))
        self.add_converter(PropConv('warm', 'fan', prop='he'))
        self.converters['ventilation'].option = {'name': f'{self.name} 换气'}
        self.converters['blow'].option = {'name': f'{self.name} 吹风'}
        self.converters['warm'].option = {'name': f'{self.name} 暖风'}
        self.converters['ventilation'].option = {'name': f'{self.name} 换气'}
        self.converters['blow'].option = {'name': f'{self.name} 吹风'}
        self.converters['warm'].option = {'name': f'{self.name} 暖风'}
        self.add_converter(PropConv('current_temp', 'sensor', prop='t', parent='heater_power'))
        self.converters['current_temp'].option = {
            'name': f'{self.name} 环境温度',
            'class': 'temperature',
            'unit': UnitOfTemperature.CELSIUS,
        }
        self.add_converter(PropConv('target_temp', 'number', prop='tgt', parent='heater_power'))
        self.converters['target_temp'].min = 1.0
        self.converters['target_temp'].max = 50.0
        self.converters['target_temp'].step = 1.0
        self.converters['target_temp'].option = {
            'name': f'{self.name} 目标环境温度',
        }
        
class SimpleSwitchDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converter(PropBoolConv('switch', 'switch', prop='p'))


class AudioDevice(XDevice):
    def setup_converters(self):
        super().setup_converters()
        self.add_converter(PropBoolConv('power', 'switch', prop='p'))
        self.converters['power'].option = {'name': '电源'}

        self.add_converter(PropConv('amv', 'number', prop='amv'))
        self.converters['amv'].min = 1.0
        self.converters['amv'].max = 100.0
        self.converters['amv'].step = 1.0
        self.converters['amv'].option = {'name': '音量'}

        asi = PropMapConv('asi', 'select', prop='asi')
        asi.map = {
            1: 'ARC',
            2: 'BD',
            3: 'GAME',
            4: 'OPT',
            5: 'COA',
            6: 'AUX',
            7: 'USB',
            8: 'BT',
        }
        asi.option = {'name': '输入选择'}
        self.add_converter(asi)

        ams = PropMapConv('ams', 'select', prop='ams')
        ams.map = {
            1: 'True 3D',
            2: 'Virtual 3D',
            3: '2.1',
            4: 'Music Hall',
        }
        ams.option = {'name': '模式选择'}
        self.add_converter(ams)

        self.add_converter(PropConv('amicvol', 'number', prop='amicvol'))
        self.converters['amicvol'].min = 1.0
        self.converters['amicvol'].max = 40.0
        self.converters['amicvol'].step = 1.0
        self.converters['amicvol'].option = {'name': 'MIC音量'}

        self.add_converter(PropConv('amicech', 'number', prop='amicech'))
        self.converters['amicech'].min = 1.0
        self.converters['amicech'].max = 40.0
        self.converters['amicech'].step = 1.0
        self.converters['amicech'].option = {'name': '效果音量'}
