import logging
from typing import Optional

from homeassistant.core import callback
from homeassistant.components.fan import (
    FanEntity,
    DOMAIN as ENTITY_DOMAIN,
    FanEntityFeature,
)

from . import (
    XDevice,
    XEntity,
    Converter,
    async_add_setuper,
)

_LOGGER = logging.getLogger(__name__)

SPEED_TO_PERCENT = {0: 0, 1: 33, 2: 66, 3: 100}
PERCENT_TO_SPEED = [(0, 0), (1, 33), (2, 66), (3, 100)]

def setuper(add_entities):
    def setup(device: XDevice, conv: Converter):
        if not (entity := device.entities.get(conv.attr)):
            entity = XFanEntity(device, conv)
        if not entity.added:
            add_entities([entity])
    return setup

async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))

class XFanEntity(XEntity, FanEntity):
    _attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF | FanEntityFeature.SET_SPEED
    _attr_is_on: Optional[bool] = None
    _attr_percentage: Optional[int] = None

    def __init__(self, device: XDevice, conv: Converter, option=None):
        super().__init__(device, conv, option)
        suffix_map = {
            'ventilation': '换气',
            'blow': '凉风',
            'warm': '暖风',
        }
        suffix = suffix_map.get(conv.attr, conv.attr)
        self._attr_name = f'{device.name} {suffix}'
        self._attr_unique_id = f'{device.id}-{conv.attr}'

    @callback
    def async_set_state(self, data: dict):
        super().async_set_state(data)
        if self._name in data:
            speed = int(data[self._name] or 0)
            self._attr_percentage = SPEED_TO_PERCENT.get(speed, 0)
            self._attr_is_on = speed > 0

    async def async_turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs):
        if percentage is None and preset_mode is None:
            speed = 3
        elif percentage is not None:
            speed = self._percent_to_speed(percentage)
        else:
            preset_map = {
                'low': 1,
                'medium': 2,
                'high': 3,
            }
            speed = preset_map.get(preset_mode, 3)
        await self.device_send_props({self._name: speed})
        self._attr_is_on = speed > 0
        self._attr_percentage = SPEED_TO_PERCENT.get(speed, 100 if speed == 3 else 66)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self.device_send_props({self._name: 0})
        self._attr_is_on = False
        self._attr_percentage = 0
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int):
        speed = self._percent_to_speed(percentage)
        await self.device_send_props({self._name: speed})
        self._attr_is_on = speed > 0
        self._attr_percentage = SPEED_TO_PERCENT.get(speed, percentage)
        self.async_write_ha_state()

    @property
    def percentage(self) -> Optional[int]:
        return self._attr_percentage

    def _percent_to_speed(self, percentage: int) -> int:
        if percentage <= 0:
            return 0
        for speed, threshold in PERCENT_TO_SPEED:
            if percentage <= threshold:
                return speed
        return 3