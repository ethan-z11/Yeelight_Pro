import logging

from homeassistant.core import callback
from homeassistant.components.select import (
    SelectEntity,
    DOMAIN as ENTITY_DOMAIN,
)

from . import (
    XDevice,
    XEntity,
    Converter,
    async_add_setuper,
)

_LOGGER = logging.getLogger(__name__)


def setuper(add_entities):
    def setup(device: XDevice, conv: Converter):
        if not (entity := device.entities.get(conv.attr)):
            entity = XSelectEntity(device, conv)
        if not entity.added:
            add_entities([entity])
    return setup


async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))


class XSelectEntity(XEntity, SelectEntity):
    def __init__(self, device: XDevice, conv: Converter, option=None):
        super().__init__(device, conv, option)
        opts = []
        self._map = getattr(conv, 'map', None)
        if isinstance(self._map, dict):
            opts = list(self._map.values())
        self._attr_options = opts or ['关闭', '智能干燥', '恒温除雾', '快速除雾', '急速加热']

    @callback
    def async_set_state(self, data: dict):
        super().async_set_state(data)
        if self._name in data:
            self._attr_current_option = data[self._name]
        elif 'heater_level' in data and isinstance(self._map, dict):
            val = data.get('heater_level')
            self._attr_current_option = self._map.get(val)
        
        if self._attr_current_option:
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        kwargs = {self._name: option}
        ret = await self.device_send_props(kwargs)
        if ret is not False:
            self._attr_current_option = option
            self.async_write_ha_state()