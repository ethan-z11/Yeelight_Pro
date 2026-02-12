import logging

from homeassistant.core import callback
from homeassistant.components.cover import (
    CoverEntity,
    DOMAIN as ENTITY_DOMAIN,
    CoverDeviceClass,
    CoverEntityFeature,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    XDevice,
    XEntity,
    Converter,
    async_add_setuper,
)

_LOGGER = logging.getLogger(__name__)


def setuper(add_entities):
    def setup(device: XDevice, conv: Converter):
        if conv.attr != 'motor':
            return
        if not (entity := device.entities.get(conv.attr)):
            entity = XCoverEntity(device, conv)
        if not entity.added:
            add_entities([entity])
    return setup


async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))


class XCoverEntity(XEntity, CoverEntity, RestoreEntity):
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN |
        CoverEntityFeature.CLOSE | 
        CoverEntityFeature.STOP |
        CoverEntityFeature.SET_POSITION
    )
    _attr_current_cover_position = 0
    _attr_is_closed = True

    def __init__(self, device: XDevice, conv: Converter, option=None):
        super().__init__(device, conv, option)
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_current_cover_tilt_position = None
        if ('target_angle' in self.subscribed_attrs or 'current_angle' in self.subscribed_attrs) or (getattr(self.device, 'pt', None) == 22):
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT |
                CoverEntityFeature.CLOSE_TILT |
                CoverEntityFeature.SET_TILT_POSITION
            )

    @callback
    def async_set_state(self, data: dict):
        super().async_set_state(data)
        
        if 'route_calibrated' in data:
            self._attr_extra_state_attributes['route_calibrated'] = bool(data['route_calibrated'])
        if 'tilt_route_calibrated' in data:
            self._attr_extra_state_attributes['tilt_route_calibrated'] = bool(data['tilt_route_calibrated'])
        
        if 'current_position' in data:
            position = data['current_position']
            self._attr_current_cover_position = position
            self._attr_is_closed = (position <= 5)
        
        if 'position' in data:
            self._attr_extra_state_attributes['target_position'] = data['position']
        
        if 'current_angle' in data:
            angle = data['current_angle']
            self._attr_extra_state_attributes['current_angle'] = angle
            try:
                self._attr_current_cover_tilt_position = max(0, min(100, round(angle * 100 / 180)))
            except Exception:
                self._attr_current_cover_tilt_position = None
            if not (self._attr_supported_features & (CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT | CoverEntityFeature.SET_TILT_POSITION)):
                self._attr_supported_features |= (
                    CoverEntityFeature.OPEN_TILT |
                    CoverEntityFeature.CLOSE_TILT |
                    CoverEntityFeature.SET_TILT_POSITION
                )
        
        if 'target_angle' in data:
            self._attr_extra_state_attributes['target_angle'] = data['target_angle']
            if not (self._attr_supported_features & (CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT | CoverEntityFeature.SET_TILT_POSITION)):
                self._attr_supported_features |= (
                    CoverEntityFeature.OPEN_TILT |
                    CoverEntityFeature.CLOSE_TILT |
                    CoverEntityFeature.SET_TILT_POSITION
                )
        
        _LOGGER.debug('%s: Cover state updated: %s', self.entity_id, {
            'position': self._attr_current_cover_position,
            'tilt': self._attr_current_cover_tilt_position,
            'is_closed': self._attr_is_closed
        })
        self.async_write_ha_state()

    @callback
    def async_restore_last_state(self, state: str, attrs: dict):
        if state:
            self.async_set_state({'run_state': state})
        if 'current_position' in attrs:
            self.async_set_state({'current_position': attrs['current_position']})

    async def async_open_cover(self, **kwargs):
        """打开窗帘"""
        await self.device_send_props({'position': 100})

    async def async_close_cover(self, **kwargs):
        """关闭窗帘"""
        await self.device_send_props({'position': 0})

    async def async_stop_cover(self, **kwargs):
        """停止窗帘"""
        await self.device_send_props({'motor': 'stop'})

    async def async_open_cover_tilt(self, **kwargs):
        await self.device_send_props({'target_angle': 180})

    async def async_close_cover_tilt(self, **kwargs):
        await self.device_send_props({'target_angle': 0})

    async def async_set_cover_tilt_position(self, **kwargs):
        tilt = kwargs.get(ATTR_TILT_POSITION)
        if tilt is not None:
            angle = max(0, min(180, int(round(tilt * 180 / 100))))
            await self.device_send_props({'target_angle': angle})

    async def async_stop_cover_tilt(self, **kwargs):
        await self.device_send_props({'motor': 'stop'})

    async def async_set_cover_position(self, **kwargs):
        position = kwargs.get(ATTR_POSITION)
        if position is not None:
            await self.device_send_props({'position': position})