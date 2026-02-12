import logging
import asyncio
import time

from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.light import (
    LightEntity,
    DOMAIN as ENTITY_DOMAIN,
    ColorMode,
    LightEntityFeature,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
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
            entity = XLightEntity(device, conv)
        if not entity.added:
            add_entities([entity])
    return setup


async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))


class XLightEntity(XEntity, LightEntity, RestoreEntity):
    _attr_is_on = None
    target_task: asyncio.Task = None

    def __init__(self, device: XDevice, conv: Converter, option=None):
        super().__init__(device, conv, option)

        self._attr_supported_color_modes = set()
        if device.converters.get(ATTR_RGB_COLOR):
            self._attr_supported_color_modes.add(ColorMode.RGB)
        if cov := device.converters.get('color_temp'):
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            if hasattr(cov, 'minm') and hasattr(cov, 'maxm'):
                self._attr_min_mireds = cov.minm
                self._attr_max_mireds = cov.maxm
            elif hasattr(cov, 'mink') and hasattr(cov, 'maxk'):
                self._attr_min_mireds = int(1000000 / cov.maxk)
                self._attr_max_mireds = int(1000000 / cov.mink)
                self._attr_min_color_temp_kelvin = cov.mink
                self._attr_max_color_temp_kelvin = cov.maxk

        if not self._attr_supported_color_modes:
            if device.converters.get(ATTR_BRIGHTNESS):
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            else:
                self._attr_supported_color_modes = {ColorMode.ONOFF}

        if device.converters.get(ATTR_TRANSITION):
            self._attr_supported_features |= LightEntityFeature.TRANSITION

        self._target_attrs = {}

    @callback
    def async_set_state(self, data: dict):
        if self.target_task:
            self.target_task.cancel()
        diff = time.time() - self._target_attrs.get('time', 0)
        delay = float(self._target_attrs.get(ATTR_TRANSITION) or 0)

        async def set_state():
            await asyncio.sleep(max(0, delay - diff + 0.01))
            super().async_set_state(data)
            self.async_write_ha_state()

        if delay > 0 and diff < delay:
            check_attrs = [ATTR_BRIGHTNESS, 'color_temp', ATTR_COLOR_TEMP_KELVIN]
            for k in check_attrs:
                if k not in data:
                    continue
                elif k not in self._target_attrs:
                    check_attrs.remove(k)
                elif self._target_attrs[k] == data[k]:
                    self._target_attrs.pop(k, None)
                    check_attrs.remove(k)
            if check_attrs:
                # ignore new state
                self.target_task = self.hass.loop.create_task(set_state())
                _LOGGER.info('%s: Ignore new state: %s', self.name, [data, self._target_attrs, diff, delay])
                return

        super().async_set_state(data)
        if self._name in data:
            self._attr_is_on = data[self._name]
        if ATTR_BRIGHTNESS in data:
            self._attr_brightness = data[ATTR_BRIGHTNESS]
        if ATTR_COLOR_TEMP_KELVIN in data:
            self._attr_color_temp_kelvin = data[ATTR_COLOR_TEMP_KELVIN]
            try:
                self._attr_color_temp = int(1000000 / float(self._attr_color_temp_kelvin))
            except Exception:
                pass
        elif 'color_temp' in data:
            self._attr_color_temp = data['color_temp']
            try:
                self._attr_color_temp_kelvin = int(1000000 / float(self._attr_color_temp))
            except Exception:
                pass
        if ATTR_RGB_COLOR in data:
            self._attr_rgb_color = data[ATTR_RGB_COLOR]
        if ATTR_RGB_COLOR in data:
            self._attr_color_mode = ColorMode.RGB
        elif (ATTR_COLOR_TEMP_KELVIN in data) or ('color_temp' in data):
            self._attr_color_mode = ColorMode.COLOR_TEMP
        
        if self._attr_is_on and self._attr_color_mode is None:
            if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            elif ColorMode.RGB in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.RGB
            elif ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.BRIGHTNESS
            elif ColorMode.ONOFF in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.ONOFF

    async def async_turn_on(self, **kwargs):
        kwargs[self._name] = True
        if ATTR_COLOR_TEMP_KELVIN in kwargs and 'color_temp' not in kwargs:
            try:
                _kelvin = int(kwargs.pop(ATTR_COLOR_TEMP_KELVIN))
                kwargs['color_temp'] = int(1000000 / float(_kelvin))
            except Exception:
                pass
        self._target_attrs = {
            **kwargs,
            'time': time.time(),
        }
        if ATTR_RGB_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGB
        elif (ATTR_COLOR_TEMP_KELVIN in kwargs) or ('color_temp' in kwargs):
            self._attr_color_mode = ColorMode.COLOR_TEMP
        else:
            if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            elif ColorMode.RGB in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.RGB
            elif ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.BRIGHTNESS
            elif ColorMode.ONOFF in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.ONOFF
            else:
                self._attr_color_mode = None
        return await self.async_turn(kwargs[self._name], **kwargs)

    async def async_turn_off(self, **kwargs):
        return await self.async_turn(False, **kwargs)

    async def async_turn(self, on=True, **kwargs):
        kwargs[self._name] = on
        ret = await self.device_send_props(kwargs)
        if ret:
            self._attr_is_on = on
            self.async_write_ha_state()
        return ret

    async def async_will_remove_from_hass(self):
        if self.target_task:
            self.target_task.cancel()
        await super().async_will_remove_from_hass()

    @callback
    def async_restore_last_state(self, state: str, attrs: dict):
        self._attr_is_on = state == 'on'
        if ATTR_BRIGHTNESS in attrs:
            self._attr_brightness = attrs.get(ATTR_BRIGHTNESS)
        kelvin = attrs.get(ATTR_COLOR_TEMP_KELVIN)
        if kelvin is not None:
            try:
                self._attr_color_temp_kelvin = int(kelvin)
                self._attr_color_temp = int(1000000 / float(self._attr_color_temp_kelvin))
            except Exception:
                pass
        ct = attrs.get('color_temp')
        if ct is not None:
            try:
                self._attr_color_temp = int(ct)
                self._attr_color_temp_kelvin = int(1000000 / float(self._attr_color_temp))
            except Exception:
                pass
        rgb = attrs.get(ATTR_RGB_COLOR)
        if rgb is not None:
            self._attr_rgb_color = rgb
            self._attr_color_mode = ColorMode.RGB
        elif (self._attr_color_temp_kelvin is not None) or (self._attr_color_temp is not None):
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif self._attr_brightness is not None:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        elif self._attr_is_on:
            if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            elif ColorMode.RGB in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.RGB
            elif ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.BRIGHTNESS
            elif ColorMode.ONOFF in self._attr_supported_color_modes:
                self._attr_color_mode = ColorMode.ONOFF
