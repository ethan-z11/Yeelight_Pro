# yeelight_pro/climate.py
"""Support for climate."""
import logging

from homeassistant.core import callback
from homeassistant.components.climate import (
    ClimateEntity,
    DOMAIN as ENTITY_DOMAIN,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.const import UnitOfTemperature

from . import (
    XDevice,
    XEntity,
    Converter,
    async_add_setuper,
)

_LOGGER = logging.getLogger(__name__)


def setuper(add_entities):
    def setup(device: XDevice, conv: Converter):
        if conv.attr.endswith('acp') and not device.entities.get(conv.attr):
            entity = XClimateEntity(device, conv)
            if not entity.added:
                add_entities([entity])
    return setup


async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))


class XClimateEntity(XEntity, ClimateEntity):
    """Yeelight Pro 空调气候实体"""
    
    _attr_hvac_modes = [HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY, HVACMode.OFF]
    _attr_fan_modes = ["low", "medium", "high"]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 1.0
    _attr_min_temp = 16.0
    _attr_max_temp = 32.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    
    def __init__(self, device: XDevice, conv: Converter, option=None):
        super().__init__(device, conv, option)
        self._channel = self._get_channel_from_attr(conv.attr)
        
        channel_suffix = f"_channel{self._channel}" if self._channel > 1 else ""
        self._attr_name = f'{device.name} 空调{self._channel if self._channel > 1 else ""}'.strip()
        self._attr_unique_id = f'{device.id}-climate{channel_suffix}'
        
        self._attr_hvac_mode = HVACMode.OFF  
        self._attr_hvac_action = HVACAction.OFF  
        self._attr_fan_mode = "medium"       
        self._attr_current_temperature = None
        self._attr_target_temperature = 24.0 
        
        self._last_power_state = False
        self._last_mode = None
        
    def _get_channel_from_attr(self, attr: str) -> int:
        if attr.startswith('1-'):
            return 1
        elif attr.startswith('2-'):
            return 2
        elif attr.startswith('3-'):
            return 3
        return 1

    @callback
    def async_set_state(self, data: dict):
        prefix = f"{self._channel}-"
        has_update = False
        current_power = None
        current_mode = None

        for k in self.subscribed_attrs:
            if k in data:
                self._attr_extra_state_attributes[k] = data[k]

        power_key = f"{prefix}acp"
        mode_key = f"{prefix}acm"

        if power_key in data:
            is_on = bool(data[power_key])
            current_power = is_on
            self._last_power_state = is_on
            if not is_on:
                if self._attr_hvac_mode != HVACMode.OFF:
                    self._attr_hvac_mode = HVACMode.OFF
                    self._attr_hvac_action = HVACAction.OFF
                    has_update = True
            else:
                if mode_key in data:
                    mode_value = data[mode_key]
                    current_mode = mode_value
                    mode_map = {
                        "cool": HVACMode.COOL,
                        "heat": HVACMode.HEAT,
                        "fan_only": HVACMode.FAN_ONLY,
                    }
                    new_mode = mode_map.get(mode_value, HVACMode.COOL)
                    if self._attr_hvac_mode != new_mode:
                        self._attr_hvac_mode = new_mode
                        has_update = True
                    self._last_mode = new_mode
                else:
                    if self._attr_hvac_mode == HVACMode.OFF:
                        fallback_mode = self._last_mode or HVACMode.COOL
                        if self._attr_hvac_mode != fallback_mode:
                            self._attr_hvac_mode = fallback_mode
                            has_update = True
        else:
            if mode_key in data:
                mode_value = data[mode_key]
                current_mode = mode_value
                mode_map = {
                    "cool": HVACMode.COOL,
                    "heat": HVACMode.HEAT,
                    "fan_only": HVACMode.FAN_ONLY,
                }
                new_mode = mode_map.get(mode_value, HVACMode.COOL)
                if self._attr_hvac_mode != new_mode:
                    self._attr_hvac_mode = new_mode
                    has_update = True
                self._last_mode = new_mode
                if self._last_power_state is False:
                    self._last_power_state = True

        if (current_power is True and current_mode) or (current_power is None and current_mode):
            action_map = {
                "cool": HVACAction.COOLING,
                "heat": HVACAction.HEATING,
                "fan_only": HVACAction.FAN,
            }
            new_action = action_map.get(current_mode, HVACAction.IDLE)
            if self._attr_hvac_action != new_action:
                self._attr_hvac_action = new_action
                has_update = True
        elif current_power is True and current_mode is None and self._attr_hvac_mode != HVACMode.OFF:
            action_map_mode = {
                HVACMode.COOL: HVACAction.COOLING,
                HVACMode.HEAT: HVACAction.HEATING,
                HVACMode.FAN_ONLY: HVACAction.FAN,
            }
            new_action = action_map_mode.get(self._attr_hvac_mode, HVACAction.IDLE)
            if self._attr_hvac_action != new_action:
                self._attr_hvac_action = new_action
                has_update = True
        elif current_power is False:
            if self._attr_hvac_action != HVACAction.OFF:
                self._attr_hvac_action = HVACAction.OFF
                has_update = True

        temp_key = f"{prefix}act"
        if temp_key in data:
            temp = data[temp_key]
            if isinstance(temp, (int, float)) and 16 <= temp <= 32:
                if self._attr_current_temperature != temp:
                    self._attr_current_temperature = temp
                    has_update = True

        target_temp_key = f"{prefix}actt"
        if target_temp_key in data:
            temp = data[target_temp_key]
            if isinstance(temp, (int, float)) and 16 <= temp <= 32:
                if self._attr_target_temperature != temp:
                    self._attr_target_temperature = temp
                    has_update = True

        fan_key = f"{prefix}acf"
        if fan_key in data:
            fan_mode = data[fan_key]
            if fan_mode in self._attr_fan_modes and self._attr_fan_mode != fan_mode:
                self._attr_fan_mode = fan_mode
                has_update = True

        if has_update:
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        prefix = f"{self._channel}-"
        _LOGGER.debug('%s: User setting HVAC mode to: %s', self.entity_id, hvac_mode)
        
        if hvac_mode == HVACMode.OFF:
            kwargs = {f"{prefix}acp": False}
            _LOGGER.debug('%s: Sending power off command: %s', self.entity_id, kwargs)
            await self.device_send_props(kwargs)
            
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
            self.async_write_ha_state()
            
        else:
            mode_map = {
                HVACMode.COOL: "cool",
                HVACMode.HEAT: "heat", 
                HVACMode.FAN_ONLY: "fan_only",
            }
            mode_value = mode_map.get(hvac_mode, "cool")
            
            kwargs = {
                f"{prefix}acp": True,
                f"{prefix}acm": mode_value
            }
            _LOGGER.debug('%s: Sending power on + mode command: %s', self.entity_id, kwargs)
            await self.device_send_props(kwargs)
            
            self._attr_hvac_mode = hvac_mode
            self._last_mode = hvac_mode
            action_map = {
                HVACMode.COOL: HVACAction.COOLING,
                HVACMode.HEAT: HVACAction.HEATING,
                HVACMode.FAN_ONLY: HVACAction.FAN,
            }
            self._attr_hvac_action = action_map.get(hvac_mode, HVACAction.IDLE)
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        prefix = f"{self._channel}-"
        
        temperature = kwargs.get("temperature")
        if temperature is not None:
            _LOGGER.debug('%s: Setting temperature to: %s', self.entity_id, temperature)
            await self.device_send_props({f"{prefix}actt": int(temperature)})
            
            self._attr_target_temperature = temperature
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        prefix = f"{self._channel}-"
        _LOGGER.debug('%s: Setting fan mode to: %s', self.entity_id, fan_mode)
        await self.device_send_props({f"{prefix}acf": fan_mode})
        
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        prefix = f"{self._channel}-"
        _LOGGER.debug('%s: Turning on AC with default cool mode', self.entity_id)
        await self.device_send_props({
            f"{prefix}acp": True,
            f"{prefix}acm": "cool"
        })
        
        self._attr_hvac_mode = HVACMode.COOL
        self._last_mode = HVACMode.COOL
        self._attr_hvac_action = HVACAction.COOLING
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        prefix = f"{self._channel}-"
        _LOGGER.debug('%s: Turning off AC', self.entity_id)
        await self.device_send_props({f"{prefix}acp": False})
        
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.OFF
        self.async_write_ha_state()

    @property
    def hvac_action(self) -> HVACAction:
        return self._attr_hvac_action