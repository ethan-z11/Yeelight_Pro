from .base import Converter
from ..const import *

class CoverConverter(Converter):
    def __init__(self):
        super().__init__("cover")
    
    def decode(self, device: 'XDevice', payload: dict, value: dict):
        if "curtain_status" in payload:
            status = payload["curtain_status"]
            value["cover"] = "open" if status == 1 else "closed"
        
        if "curtain_position" in payload:
            position = payload["curtain_position"]
            value["cover_position"] = position
    
    def encode(self, device: 'XDevice', payload: dict, value):
        if "cover" in value:
            state = value["cover"]
            if state == "open":
                payload["curtain_control"] = 1
            elif state == "close":
                payload["curtain_control"] = 2
            elif state == "stop":
                payload["curtain_control"] = 0
        
        if "cover_position" in value:
            position = value["cover_position"]
            payload["curtain_position"] = position
    
    def options(self, device: 'XDevice') -> dict:
        return {
            "class": "curtain",
            "translation_key": "curtain"
        }