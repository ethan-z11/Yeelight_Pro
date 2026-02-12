from enum import IntEnum  

DOMAIN = 'yeelight_pro'
DEFAULT_NAME = 'Yeelight Pro'

CONF_GATEWAYS = 'gateways'

SUPPORTED_DOMAINS = [
    'button',
    'sensor',
    'switch',
    'light',
    'number',
    'binary_sensor',
    'cover',
    'climate',
    'fan',
    'select',
]

PID_GATEWAY = 1
PID_WIFI_PANEL = 2
PID_CURTAIN = "curtain" 

SERVICE_SET_POSITION = "set_cover_position"


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
    SWITCH_SENSOR = 128
    MOTION_SENSOR = 129
    MAGNET_SENSOR = 130
    KNOB = 132
    MOTION_WITH_LIGHT = 134
    ILLUMINATION_SENSOR = 135
    TEMPERATURE_HUMIDITY = 136

DEVICE_TYPE_LIGHTS = [
    DeviceType.LIGHT,
    DeviceType.LIGHT_WITH_BRIGHTNESS,
    DeviceType.LIGHT_WITH_COLOR_TEMP,
    DeviceType.LIGHT_WITH_COLOR,
    DeviceType.LIGHT_WITH_ZOOM_CT,
]
