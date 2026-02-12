import logging
from homeassistant.components.event import (
    EventEntity,
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
            entity = YeelightProEvent(device, conv)
        if not entity.added:
            add_entities([entity])
    return setup


async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))


class YeelightProEvent(XEntity, EventEntity):
    
    def __init__(self, device: XDevice, conv: Converter):
        super().__init__(device, conv)
        if hasattr(conv, 'event_types'):
            self._attr_event_types = conv.event_types

    def async_set_state(self, data: dict):
        """Handle event."""
        if self._name in data:
            event_data = data[self._name]
            event_type = event_data.get('type')
            
            type_map = {
                'panel.click': '点击',
                'panel.hold': '长按',
                'panel.release': '松开'
            }
            
            if event_type in type_map:
                mapped_type = type_map[event_type]
                if mapped_type in self._attr_event_types:
                    self._trigger_event(mapped_type, event_data)
                    self.async_write_ha_state()
