import re

from palworld_save_tools.archive import *
import json
import copy

def toUUID(uuid_str):
    if isinstance(uuid_str, UUID):
        return uuid_str
    return UUID.from_str(str(uuid_str))

class PalObject:
    @staticmethod
    def toUUID(uuid_str):
        if isinstance(uuid_str, UUID):
            return uuid_str
        return UUID.from_str(str(uuid_str))

    @staticmethod
    def IntProperty(val):
        return {'id': None, 'type': 'IntProperty', 'value': val}

    @staticmethod
    def StrProperty(val):
        return {'id': None, 'type': 'StrProperty', 'value': val}

    @staticmethod
    def EnumProperty(type, val):
        return {'id': None, 'type': 'EnumProperty', 'value': {
            'type': type,
            'value': val
        }}
    
    @staticmethod
    def BoolProperty(val):
        return {'id': None, 'type': 'BoolProperty', 'value': val}

    @staticmethod
    def FloatProperty(val):
        return {'id': None, 'type': 'FloatProperty', 'value': val}
    
    @staticmethod
    def ArrayProperty(array_type, val, custom_type=None):
        rc = {'id': None, 'type': 'ArrayProperty', "array_type": array_type, 'value': val}
        if custom_type is not None:
            rc['custom_type'] = custom_type
        return rc

    @staticmethod
    def Guid(guid):
        return {'id': None,
                'struct_id': toUUID('00000000-0000-0000-0000-000000000000'),
                'struct_type': 'Guid',
                'type': 'StructProperty',
                'value': toUUID(guid)
                }

    @staticmethod
    def FixedPoint64(value):
        return {
            "struct_type": "FixedPoint64",
            "struct_id": PalObject.toUUID("00000000-0000-0000-0000-000000000000"),
            "id": None,
            "value": {
                "Value": {
                    "id": None,
                    "value": value,
                    "type": "Int64Property"
                }
            },
            "type": "StructProperty"
        }

    @staticmethod
    def Vector(x, y, z):
        return {
            "struct_type": "Vector",
            "struct_id": PalObject.toUUID("00000000-0000-0000-0000-000000000000"),
            "id": None,
            "value": {
                "x": x,
                "y": y,
                "z": z
            },
            "type": "StructProperty"
        }

    @staticmethod
    def PalContainerId(container_id):
        return {"id": None,
                "type": "StructProperty",
                "struct_id": toUUID('00000000-0000-0000-0000-000000000000'),
                "struct_type": "PalContainerId",
                "value": {
                    'ID': PalObject.Guid(container_id)
                }
                }

    @staticmethod
    def PalInstanceID(InstanceId, PlayerUId):
        return {"id": None,
                "type": "StructProperty",
                "struct_id": toUUID('00000000-0000-0000-0000-000000000000'),
                "struct_type": "PalInstanceID",
                "value": {
                    "DebugName": PalObject.StrProperty(""),
                    "InstanceId": PalObject.Guid(InstanceId),
                    "PlayerUId": PalObject.Guid(PlayerUId),
                }
                }

    @staticmethod
    def PalCharacterSlotId(container_id, slotIndex):
        return {
            "id": None,
            "type": "StructProperty",
            "struct_id": toUUID('00000000-0000-0000-0000-000000000000'),
            "struct_type": "PalCharacterSlotId",
            "value": {
                "ContainerId": PalObject.PalContainerId(container_id),
                "SlotIndex": PalObject.IntProperty(slotIndex)
            }
        }

    @staticmethod
    def PalCharacterSlotSaveData_Array(InstanceId, PlayerUId, characterInstanceId):
        rawData = PalObject.ArrayProperty("ByteProperty", {
            'instance_id': toUUID(characterInstanceId),
            'permission_tribe_id': 0,
            'player_uid': toUUID(PlayerUId)
        })
        rawData['custom_type'] = ".worldSaveData.CharacterContainerSaveData.Value.Slots.Slots.RawData"

        return {
            'IndividualId': PalObject.PalInstanceID(InstanceId, PlayerUId),
            'PermissionTribeID': PalObject.EnumProperty('EPalTribeID', 'EPalTribeID::GrassMammoth'),
            'RawData': rawData
        }

    @staticmethod
    def PalItemContainerBelongInfo(GroupID):
        return {
            "id": None,
            "type": "StructProperty",
            "struct_id": toUUID('00000000-0000-0000-0000-000000000000'),
            "struct_type": "PalItemContainerBelongInfo",
            "value": {
                "GroupID": PalObject.Guid(GroupID)
            }
        }

    @staticmethod
    def PalItemId():
        return {'id': None,
                'struct_id': toUUID('00000000-0000-0000-0000-000000000000'),
                'struct_type': 'PalItemId',
                'type': 'StructProperty',
                'value': {'DynamicId': {'id': None,
                                        'struct_id': toUUID(
                                            '00000000-0000-0000-0000-000000000000'),
                                        'struct_type': 'PalDynamicItemId',
                                        'type': 'StructProperty',
                                        'value': {'CreatedWorldId': {'id': None,
                                                                     'struct_id': toUUID(
                                                                         '00000000-0000-0000-0000-000000000000'),
                                                                     'struct_type': 'Guid',
                                                                     'type': 'StructProperty',
                                                                     'value': toUUID(
                                                                         '00000000-0000-0000-0000-000000000000')},
                                                  'LocalIdInCreatedWorld': {'id': None,
                                                                            'struct_id': toUUID(
                                                                                '00000000-0000-0000-0000-000000000000'),
                                                                            'struct_type': 'Guid',
                                                                            'type': 'StructProperty',
                                                                            'value': toUUID(
                                                                                '00000000-0000-0000-0000-000000000000')}}},
                          'StaticId': {'id': None,
                                       'type': 'NameProperty',
                                       'value': 'Stone'}}}

    @staticmethod
    def PalItemSlotSaveData_Array():
        return {
            {'ItemId': PalObject.PalItemId(),
             'RawData': PalObject.ArrayProperty("ByteProperty", {'corruption_progress_value': 0.0,
                                                                       'permission': {'item_static_ids': [],
                                                                                      'type_a': [],
                                                                                      'type_b': []}},
                                                      ".worldSaveData.ItemContainerSaveData.Value.Slots.Slots.RawData"),
             'SlotIndex': PalObject.IntProperty(0),
             'StackCount': PalObject.IntProperty(0)
             }
        }

    @staticmethod
    def PalItemSlotSaveData_Slots():
        return {
            'id': toUUID('00000000-0000-0000-0000-000000000000'),
            'prop_name': 'Slots',
            'prop_type': 'StructProperty',
            'type_name': 'PalItemSlotSaveData',
            'values': []
        }

    @staticmethod
    def ItemContainerSaveData_Array(InstanceId):
        return {
            'key': {
                'ID': PalObject.Guid(InstanceId)
            },
            'value': {
                'BelongInfo': PalObject.PalItemContainerBelongInfo("00000000-0000-0000-0000-000000000000"),
                "RawData": PalObject.ArrayProperty("ByteProperty", {
                    'permission': {'item_static_ids': [],
                                   'type_a': [],
                                   'type_b': []}
                }, ".worldSaveData.ItemContainerSaveData.Value.RawData"),
                "Slots": PalObject.ArrayProperty("StructProperty", PalObject.PalItemSlotSaveData_Slots())
            }
        }


class JsonPalSimpleObject:
    type = None
    value = None
    custom_type = None
    
    def __init__(self, _type, _value, custom_type=None):
        self.type = _type
        self.value = _value
        self.custom_type = custom_type

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return f"PalObject.toUUID('{str(obj)}')"
        elif isinstance(obj, JsonPalSimpleObject):
            if obj.custom_type is not None:
                return f"PalObject.{obj.type}({repr(obj.value)}, {repr(obj.custom_type)})"
            else:
                return f"PalObject.{obj.type}({repr(obj.value)})"
        return super(CustomEncoder, self).default(obj)

def AutoMakeStruct(struct):
    structs = {}
    if 'type' in struct and struct['type'] == "StructProperty":
        print(f"proc struct {struct['struct_type']}")
        if struct['struct_type'] in ["Vector"]:
            return structs
        for k in struct['value']:
            if isinstance(struct['value'][k], JsonPalSimpleObject):
                continue
            if struct['value'][k]['type'] in ['IntProperty', 'StrProperty', 'BoolProperty', 'FloatProperty']:
                struct['value'][k] = JsonPalSimpleObject(struct['value'][k]['type'], struct['value'][k]['value'])
            elif struct['value'][k]['type'] == 'StructProperty':
                structs.update(AutoMakeStruct(struct['value'][k]))
                struct['value'][k] = JsonPalSimpleObject(struct['value'][k]['struct_type'], None)
            elif struct['value'][k]['type'] == 'ArrayProperty':
                # struct['value'][k]['value']['values'][0]
                struct['value'][k] = JsonPalSimpleObject("ArrayProperty", struct['value'][k]['array_type'], struct['value'][k]['custom_type'] if 'custom_type' in struct['value'][k] else None)
        if struct['struct_type'] not in dir(PalObject):
            structs[struct['struct_type']] = "    @staticmethod\n" + \
                 f"    def {struct['struct_type']}():\n" + \
                 f"        return "  + re.sub(r"\"PalObject\.(.+)\",?", "PalObject.\\1,", json.dumps(struct, indent=4, cls=CustomEncoder).replace("\n", "\n        "))
    return structs

# print("\n\n".join(AutoMakeStruct(copy.deepcopy(MappingCache.CharacterSaveParameterMap[toUUID('1dd8d2a0-4dd7-4b05-f3c0-7ab60ebd95e4')]['value']['RawData']['value']['object']['SaveParameter'])).values()))

# print("".join(AutoMakeStruct({"type":"StructProperty","struct_type":"A","value":s['value']['Slots']['value']['values'][0]}).values()))