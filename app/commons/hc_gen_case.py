import re
import json
import copy
import base64
import numbers
import logging
import jsonpath_ng
import time
import random
import binascii
from flask import current_app, Flask
# --------
# TODO
# Known issue
# sort range list for RANGE type

# We have base API case (minimum && can call successfully)
# Each time modify only one field

ERROR_CODE_LIST_SPEX_SUCCESS = [0]
ERROR_CODE_LIST_SPEX_ERROR = [105]

INT_TYPE = ["INT32", "INT64", "UINT32", "UINT64"]
FLOAT_TYPE = ["DOUBLE", "FLOAT"]
STRING_TYPE =["STRING", "BYTES"]
NESTED_TYPE = ["LIST", "DICT", "RECURSIVE"]
NUMBER_TYPE = INT_TYPE + FLOAT_TYPE
BASIC_TYPE = NUMBER_TYPE + STRING_TYPE + ["BOOL"]
ALL_TYPE = NUMBER_TYPE + STRING_TYPE + NESTED_TYPE + ["BOOL"]
CAN_USE_UNIQUE_TYPE = NUMBER_TYPE + STRING_TYPE

RANGE_TYPE = ["NONE","RANGE","ENUM"]
SKIP_CHECKING_TYPE = ["RECURSIVE"]
DEFAULT_NONE_RANGE_TYPE = ["DICT","LIST","RECURSIVE","STRING","BYTES"]
DOUBLE_MAX = 1.7976931348623158E+308  # 64 bit floating point max value
DOUBLE_MIN = 2.2250738585072014E-308  # 64 bit floating point max value
FLOAT_MAX = 3.402823466E+38  # 32 bit floating point max value
FLOAT_MIN = 1.175494351E-38
# CONST for biz
REGION = ["SG","ID","MY","PH","TH","VN","TW","BR","MX","CO","CL","FR","ES","PL","AR","IN"]
USERID = 1215587845
USERNAME = "apiautocheck"

RE_REMOVE_SPACE = re.compile(r'\s')
RE_GET_FIELD_NAMES = re.compile(r'\{\{(.+?)\}\}')
RE_GET_OPERATORS = re.compile(r'\{\{.*?\}\}')
SUPPORTED_COMBINATION_RULES_OPERATORS = ["&&","||","and","or","AND","OR"]

class CustomError(Exception):
    """to raise error from basic error and add more info"""
    pass

def serialize_bytes(obj):
    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    raise TypeError ("Type %s is not serializable" % type(obj))

def serialize_bytes_base64(obj):
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode('utf-8')
    raise TypeError ("Type %s is not serializable" % type(obj))

def get_type(field_type):
    if type(field_type) is str:
        return field_type
    elif type(field_type) is list:
        return "LIST"
    elif type(field_type) is dict:
        return "DICT"


def get_empty_value(field_type: str):
    field_type = field_type.upper()
    if field_type == 'INT32' or field_type == 'INT64' or field_type == 'UINT32' or field_type == 'UINT64':
        return 0
    elif field_type == 'STRING':
        return ''
    elif field_type == 'BOOL':
        return False
    elif field_type == 'FLOAT':
        return 0.0
    elif field_type == 'DOUBLE':
        return 0.0
    elif field_type == 'BYTES':
        return b''
    elif field_type == 'LIST':
        return []
    elif field_type == 'DICT':
        return {}
    elif field_type == 'RECURSIVE':
        return None
    else:
        current_app.logger.warning(f"No empty value set for type: {field_type}")
        return None


def get_type_default_value(field_type: str):
    field_type = field_type.upper()
    if field_type == 'INT32' or field_type == 'INT64' or field_type == 'UINT32' or field_type == 'UINT64':
        return 1
    elif field_type == 'STRING':
        return 'a'
    elif field_type == 'BOOL':
        return True
    elif field_type == 'FLOAT':
        return 1.0
    elif field_type == 'DOUBLE':
        return 1.0
    elif field_type == 'LIST':
        return []
    elif field_type == 'DICT':
        return {}
    elif field_type == 'BYTES':
        return b'a'
    elif field_type == 'NUMBER':
        return 1
    elif field_type == 'RECURSIVE':
        return None
    else:
        current_app.logger.warning(f"No default value set for type: {field_type}")
        return None


def get_wrong_type_value(field_type: str):
    field_type = field_type.upper()
    if field_type == 'INT32' or field_type == 'INT64' or field_type == 'UINT32' or field_type == 'UINT64':
        return 3
    elif field_type == 'STRING':
        return 'a'
    elif field_type == 'BOOL':
        return True
    elif field_type == 'FLOAT':
        return 3.0
    elif field_type == 'DOUBLE':
        return 3.0
    elif field_type == 'LIST':
        return [3]
    elif field_type == 'DICT':
        return {"a": 3}
    elif field_type == 'BYTES':
        return b'a'
    elif field_type == 'NUMBER':
        return 3
    elif field_type == 'RECURSIVE':
        return None
    else:
        current_app.logger.warning(f"No default value set for type: {field_type}")
        return None


def get_type_range(field_type: str):
    field_type = field_type.upper()
    if field_type == 'INT32':
        return [-2147483648, 2147483647]
    elif field_type == 'INT64':
        return [-9223372036854775808, 9223372036854775807]
    elif field_type == 'UINT32':
        return [0, 4294967295]
    elif field_type == 'UINT64':
        return [0, 18446744073709551615]
    elif field_type == "DOUBLE":
        return [DOUBLE_MIN, DOUBLE_MAX]
    elif field_type == "FLOAT":
        return [FLOAT_MIN, FLOAT_MAX]
    elif field_type == 'BOOL':
        return [False, True]
    elif field_type in STRING_TYPE:
        return [0, None]
    elif field_type in ["LIST","DICT","RECURSIVE"]:
        return [None,None]
    else:
        current_app.logger.warning(f"No supported range for type: {field_type}")
        return []

#
# # request sample
# {
#     "bff_meta": {
#         "app_type": "INT32",
#         "app_version": "STRING",
#         "client_id": "STRING", "client_ip": "STRING", "client_ip_country": "STRING", "client_platform": "UINT32",
#         "cookies": [
#             {"domain": "STRING", "http_only": "BOOL", "max_age": "INT32", "name": "STRING", "path": "STRING",
#             "secure": "BOOL", "value": "STRING"}
#         ],
#         "country": "STRING", "device_fingerprint": "STRING",
#         "downgrade": "BOOL", "language": "STRING", "platform": "INT32", "rn_version": "STRING",
#         "session_id": "STRING", "shopee_token": "STRING", "shopid": "INT32", "sso_token": "STRING",
#         "tracking_session_id": "STRING", "url": "STRING", "user_agent": "STRING", "userid": "INT32"
#     }
# }

# # response sample
# {"bff_meta": {"content_type": "STRING",
#               "cookies": [{"domain": "STRING", "http_only": "BOOL", "max_age": "INT32", "name": "STRING",
#                            "path": "STRING", "secure": "BOOL", "value": "STRING"}]},
#  "data": {"child_request_id": "STRING"}, "error": "INT32", "error_msg": "STRING"}
#
# # errors sample
# {"ERROR_MOCK_COMMAND_NOT_FOUND": 16300001, "ERROR_MOCK_COMMAND_TEST_ERROR": 16300002,
#  "ERROR_MOCK_COMMAND_DECODE_ERROR": 16300003,
#  "ERROR_MOCK_COMMAND_HTTP_REQUEST_ERROR": 16300004, "ERROR_MOCK_COMMAND_TCP_REQUEST_ERROR": 16300005,
#  "ERROR_MOCK_COMMAND_UNMARSHAL_ERROR": 16300006}

# user_input_cases is not supported in Phase 1
old_template_of_one_API = {
    'request': {
        'field_name1': {
            'type': 'STRING',
            'range_type':'range',
            'range': [],
            'is_required': False,
            'allow_empty': False,
            'skip_checking': False,
            'default_value': 3,
            'user_input_cases': [
                {
                    'value': 1,
                    'check': [
                        {
                            'type': 'error_code/response',
                            'item': 'json.path',
                            'value': [1001, 1001, 10002, 10004]
                        }
                    ]
                }
            ]
        }
    },
    'response': {
    },
    'error_code_list': []
}
# to support parent-children UI
new_template_of_one_API = {
    'request': {
        'field_name1': {
            'type': 'DICT', ## DICT / LIST / RECURSIVE will have children
            'range_type':'range',
            'range': [],
            'is_required': False,
            'allow_empty': False,
            'skip_checking': False,
            'default_value': None, # deprecate this field
            'children':[ 
                {
                    'sub_field_name1': {
                        ### atrributes
                        ### ...
                    }
                },
                {
                    'sub_field_name2': {
                        ### atrributes
                        ### ...
                    }
                },
            ],
            'user_input_cases': [
            ]
        },
        'field_name2': {
            'type': 'LIST', ## DICT / LIST / RECURSIVE will have children
            'range_type':'range',
            'range': [],
            'is_required': False,
            'allow_empty': False,
            'skip_checking': False,
            'default_value': None, # deprecate this field
            'children':[ 
                {
                    '0':{
                        ### atrributes
                        ### ...
                    }
                    
                }
            ],
            'user_input_cases': [
            ]
        },
    },
    'response': {
    },
    'default_request':'{}',
    'combination_rules':[],
    'error_code_list': [],
    "user_specified_errors": {
        "enum_error": [
        118800001
        ],
        "boundary_error": [
        118800002
        ],
        "empty_error": [
        118800020,
        118800002
        ],
        "required_error": [
        118800022
        ],
        "combination_error":[
            118800022
        ]
  }
}

def split_field_name(key_name):
    result = []
    if '[' in key_name:
        result.append(key_name.split('[')[0])
        result.extend(re.findall(r'\[\d\]',key_name))
    else:
        result.append(key_name)
    return result

def split_by_rightmost_delimeter(field_name):
    index = max(field_name.rfind('['),field_name.rfind('.'))
    if index == -1:
        return field_name, "", 'NONE'
    prefix = field_name[:index]
    suffix = field_name[index:]
    delimeter_type = 'DICT'
    if '.' in suffix:
        suffix = suffix[1:]
    elif '[' in suffix:
        delimeter_type = 'LIST'
        suffix = suffix[1:-1]
    return prefix, suffix, delimeter_type

## convert from old_template_of_one_API to new_template_of_one_API
## convert template.request from flat to parent-child node
def structurize_template(template):
    if "request" not in template:
        err_msg = f"Template doesn't have request field: {template}"
        current_app.logger.error(err_msg)
        raise Exception(err_msg)
    # template = copy.deepcopy(template)
    reversed_sorted_req = dict(sorted(template["request"].items(),reverse=True))
    new_req = {}

    for field_name, field_value in reversed_sorted_req.items():
        prefix, suffix, delimeter_type = split_by_rightmost_delimeter(field_name)
        if delimeter_type in ['DICT','LIST']:
            if 'children' not in reversed_sorted_req[prefix]:
                reversed_sorted_req[prefix]['children'] = []
            # reversed_sorted_req[prefix]['children'].append({suffix:field_value})
            reversed_sorted_req[prefix]['children'].append(field_value)
        elif delimeter_type == 'NONE':
            new_req[field_name] = reversed_sorted_req[field_name]
    template["request"] = new_req
    current_app.logger.log(2,f'func structurize_template: {json.dumps(template,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
    return template

def extract_child_node(root,result={},prefix=""):
    for field_name, field_value in root.items():
        if field_name.isdigit():
            current_name = f'{prefix}[{field_name}]' if prefix else field_name
        else:
            current_name = f'{prefix}.{field_name}' if prefix else field_name
        if "children" in field_value:
            for elem in field_value["children"]:
                temp_name = elem["name"]
                if '[' in elem["name"]:
                    temp_name = temp_name[1:-1]
                extract_child_node({temp_name:elem}, result, current_name)
            field_value.pop("children")
            result[current_name] = field_value
        else:
            result[current_name] = field_value
            current_name = prefix
    return result

## convert from new_template_of_one_API to old_template_of_one_API
## convert template.request from parent-child node to flat
def flatten_template(template):
    if "request" not in template:
        err_msg = f"Template doesn't have request field: {template}"
        current_app.logger.error(err_msg)
        raise Exception(err_msg)
    temp_req = template["request"]
    flat_req = {}
    res = extract_child_node(temp_req,flat_req)
    template["request"] = flat_req
    current_app.logger.log(2,f'func flatten_template: {json.dumps(template,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
    return template

def gen_default_value(default_request, input):
    if isinstance(input,dict):
        for field_name, field_type in input.items():
            if isinstance(field_type,dict):
                default_request[field_name] = {}
                gen_default_value(default_request[field_name], input[field_name])
            elif isinstance(field_type,list):
                default_request[field_name] = []
                res = []
                gen_default_value(res,input[field_name])
                default_request[field_name] = res
            else:
                default_request[field_name] = get_type_default_value(field_type)


    elif isinstance(input,list):
        for element in input:
            if isinstance(element,dict):
                res = {}
                gen_default_value(res, element)
                default_request.append(res)
            elif isinstance(element,list):
                res = []
                gen_default_value(res,element)
                default_request.append(res)
            else:
                default_request.append(get_type_default_value(element))
    



def gen_default_request_and_template_request(input, default_request,template_request={},prefix=""):
    if isinstance(input,dict):
        for field_name, field_type in input.items():
            template_field_name = prefix + field_name if prefix else field_name
            template_request[template_field_name] = build_field_attribute(field_name, field_type, template_field_name)
            if isinstance(field_type,dict):
                default_request[field_name] = {}
                gen_default_request_and_template_request(input[field_name], default_request[field_name], template_request, template_field_name+".")
            elif isinstance(field_type,list):
                default_request[field_name] = []
                res = []
                gen_default_request_and_template_request(input[field_name],res,template_request, template_field_name)
                default_request[field_name] = res
            else:
                default_request[field_name] = get_type_default_value(field_type)
                # only non-list field has special business logic attribute
                special_attribute = get_business_logic_attribute(field_name, field_type)
                if "default_value" in special_attribute:
                    default_request[field_name] = special_attribute["default_value"]

    elif isinstance(input,list):
        for index, element in enumerate(input):
            template_field_name = prefix + f'[{index}]' if prefix else f'[{index}]'
            template_request[template_field_name] = build_field_attribute(index, element, template_field_name)
            if isinstance(element,dict):
                res = {}
                gen_default_request_and_template_request(element, res, template_request, f"{template_field_name}.")
                default_request.append(res)
            elif isinstance(element,list):
                res = []
                gen_default_request_and_template_request(element, res, template_request, f"{template_field_name}")
                default_request.append(res)
            else:
                default_request.append(get_type_default_value(element))

def extract_path_list(path):
    return re.findall(r'([^\[\]\.]+)',path)

## this is to gen and return field attribute
## will update 'range_type', 'range', 'type' according to field_name and field_type
def build_field_attribute(field_name,field_type, path):
    field_type = get_type(field_type)
    is_list_elem = True if isinstance(field_name,int) else False
    path_list = extract_path_list(path)
    field_attribute = {
        'name': f'[{str(field_name)}]' if is_list_elem else field_name,
        'path': path_list,
        'is_required': False,
        'allow_empty': True,
        'can_be_unique': field_type in CAN_USE_UNIQUE_TYPE,
        'use_unique_value': False,
        'skip_checking': get_skip_checking(field_type),
        'range_type': get_type_range_type(field_type),
        'range': get_type_range(field_type),
        'type': field_type,
        'user_input_cases': [],
    }

    # TODO
    # special logic to make field attribute more suitable
    if not is_list_elem:
        special_attribute = get_business_logic_attribute(field_name, field_type)
        for key, value in special_attribute.items():
            if key != "default_value":
                field_attribute[key] = value
            
    return field_attribute
        
def get_business_logic_attribute(field_name, field_type):
    field_name = field_name.lower()
    field_type = field_type.upper()
    special_attribute = {}
    if field_name == "region" and field_type == "STRING":
        special_attribute["default_value"] = "SG"
        special_attribute["allow_empty"] = False
        special_attribute["range_type"] = "ENUM"
        special_attribute["range"] = REGION
    elif (field_name == "user_id" or field_name == "userid") and field_type in NUMBER_TYPE:
        special_attribute["default_value"] = USERID
        special_attribute["range_type"] = "NONE"
    return special_attribute

# deprecated
def gen_field_attribute(field_value, field_key=""):
    field_type = get_type(field_value)
    req = {}
    field_attribute = {
        'is_required': False,
        'allow_empty': True,
        'skip_checking': False,
        'user_input_cases': [],
        'range_type':'RANGE',
        'range': [],
        # 'default_value': None,
        'type': field_type
    }
    if field_type == "LIST":
        list_type = field_value[0]
        temp = gen_field_attribute(list_type, field_key + "[0]")
        req = dict(req, **temp)
        # field_attribute["children"] = gen_field_attribute(list_type,"list_type")
        field_attribute["range_type"] = get_type_range_type(field_type)
        req[field_key] = field_attribute
    elif field_type == "DICT":
        for key, value in field_value.items():
            if field_key == "":
                subkey = key
            else:
                subkey = field_key + '.' + key
            temp = gen_field_attribute(value, subkey)
            req = dict(req, **temp)
            if field_key != "":
                field_attribute["range_type"] = get_type_range_type(field_type)
                req[field_key] = field_attribute
    else:
        field_attribute["default_value"] = get_type_default_value(field_type)
        set_range_attribute(field_key,field_type,field_attribute)
        req[field_key] = field_attribute
    return req

# deprecated
def set_range_attribute(field_name,field_type,field_attribute):
    field_attribute["range"] = get_type_range(field_type)
    field_attribute["range_type"] = get_type_range_type(field_type)

    # TODO
    # special logic to make range more suitable
    field_name = field_name.lower()
    field_type = field_type.upper()
    if field_type == "RECURSIVE" or field_type == "BYTES":
        field_attribute["range_type"] = "NONE"
        field_attribute["skip_checking"] = True
    elif field_name == "region" and field_type == "STRING":
        field_attribute["default_value"] = "SG"
        field_attribute["range_type"] = "ENUM"
        field_attribute["range"] = REGION
    elif (field_name == "user_id" or field_name == "userid") and field_type in NUMBER_TYPE:
        field_attribute["default_value"] = USERID
        field_attribute["range_type"] = "NONE"
        

def get_type_range_type(field_type):
    field_type = field_type.upper()
    if field_type in NUMBER_TYPE:
        return "RANGE"
    elif field_type == 'BOOL':
        return "RANGE"
    elif field_type in DEFAULT_NONE_RANGE_TYPE:
        return "NONE"
    else:
        current_app.logger.warning(f"No supported range for type: {field_type}")
        return "NONE"

def get_skip_checking(field_type):
    field_type = field_type.upper()
    if field_type in SKIP_CHECKING_TYPE:
        return True
    return False

def default_template(request, response={}, error_code_list=[]):
    '''
    args:
        request: cmd body, dict
        response: cmd body, dict
    generate default template for an API
    return :
        template body
    '''
    request = copy.deepcopy(request)
    response = copy.deepcopy(response)
    default_request = {}
    template_request = {}
    resp = {}
    # req = gen_field_attribute(request)
    # TODO gen resp & get errorcode
    gen_default_request_and_template_request(request,default_request,template_request)
    template = {
        "request": template_request,
        "response": resp,
        "default_request": json.dumps(default_request, indent=4, default=serialize_bytes_base64), # json string
        "combination_rules": [],
        "error_code_list": error_code_list,
        "user_specified_errors": {}
    }

    # convert ranges to str
    # TODO: we don't handle javascript number overflow for default value for now
    for key, value in template["request"].items():
        if value["type"] in NUMBER_TYPE or (value["type"] in STRING_TYPE and value["range_type"] == "RANGE"):
            value["range"] = list(map(convert_number_to_str,value["range"]))
    current_app.logger.log(5,f'default template:\n{json.dumps(template,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
    return template

def is_correct_type(value,field_type):
    if value == None:
        return True
    if field_type == 'INT32' or field_type == 'INT64' or field_type == 'UINT32' or field_type == 'UINT64':
        if isinstance(value,int):
            return True
        else:
            return False
    elif field_type in STRING_TYPE:
        if isinstance(value,str):
            return True
        else:
            return False
    elif field_type == 'BOOL':
        if isinstance(value,bool):
            return True
        else:
            return False
    elif field_type == 'FLOAT' or field_type == 'DOUBLE':
        if isinstance(value,float):
            return True
        else:
            return False
    elif field_type == 'LIST':
        if isinstance(value,list):
            return True
        else:
            return False
    elif field_type == 'DICT':
        if isinstance(value,dict):
            return True
        else:
            return False
    else:
        current_app.logger.warning(f"type [{field_type}] is not supported. Failed silently")
        return True


def check_default_request(template):
    err_msg = ""
    if "default_request" not in template:
        pass
        # err_msg += "[default_request] no default request in API template\n"
    else:
        current_app.logger.log(2,f'default_request: {template["default_request"]}')
        try:
            default_req = json.loads(template["default_request"])
            check_default_req_msg = process_json(check_default_request_logic, default_req, template["request"])
            err_msg += check_default_req_msg
        except CustomError as err:
            current_app.logger.error(f'{err}')
            err_msg += f"{err}\n"
        except json.decoder.JSONDecodeError as err:
            current_app.logger.error(f'[default_request] load json failed:\n original request: {template["default_request"]}. \n err: {err}')
            err_msg += f"[default_request] invalid default request json format. {err}\n"
        except Exception as err:
            current_app.logger.error(f'[default_request] failed to check default request:\n err: {type(err).__name__} {err}')
            err_msg += f'[default_request] failed to check default request:\n err: {type(err).__name__} {err}'
    return err_msg

# check value type only, doesn't check value range now
# implement process_json handle function
def check_default_request_logic(field_value,field_attribute):
    err_msg = ""
    field_type = field_attribute["type"]
    if not is_correct_type(field_value, field_type):
        err_msg += f"type should be {field_type} rather than {type(field_value)}. "
    if field_attribute["type"] == "BYTES":
        try:
            base64.b64decode(field_value)
        except Exception as err:
            err_msg += f"failed to convert from bytes string to bytes. {err}\n"
    return err_msg

# implement process_json handle function
def convert_b64str_to_bytes_in_default_request(field_value,field_attribute):
    err_msg = ""
    if field_attribute["type"] == "BYTES":
        try:
            base64.b64decode(field_value)
        except Exception as err:
            err_msg += f"failed to convert from bytes string to bytes. {err}\n"
    return err_msg


def process_json(handle_func, input, input_attribute, prefix=""):
    err_msg = ""
    if isinstance(input,dict):
        for field_name, field_type in input.items():
            template_field_name = prefix + field_name if prefix else field_name
            res = handle_func(field_type, input_attribute[template_field_name])
            if res:
                err_msg += f'[default_request] {template_field_name}: {res}'
            if isinstance(field_type,dict):
                err_msg += process_json(handle_func, input[field_name], input_attribute, template_field_name+".")
            elif isinstance(field_type,list):
                err_msg += process_json(handle_func, input[field_name], input_attribute, template_field_name)
            else:
                pass

    elif isinstance(input,list):
        for index, element in enumerate(input):
            ### as for now, template only has one element for list. So here we use fixed first element
            # template_field_name = prefix + f'[{index}]' if prefix else f'[{index}]'
            template_field_name = prefix + f'[0]' if prefix else f'[0]'
            res = handle_func(element, input_attribute[template_field_name])
            if res:
                err_msg += f'[default_request] {template_field_name}: {res}'
            if isinstance(element,dict):
                err_msg += process_json(handle_func, element, input_attribute, f"{template_field_name}.")
            elif isinstance(element,list):
                err_msg += process_json(handle_func, element, input_attribute, f"{template_field_name}")
            else:
                pass
    return err_msg

# check number of operator & fields, if field in template request, if operator is supported
def check_combination_rules(template):
    err_msg = ""
    template_req = template["request"]
    rules = template["combination_rules"]

    for rule in rules:
        if not rule:
            continue
        rule = RE_REMOVE_SPACE.sub("", rule)
        field_names = RE_GET_FIELD_NAMES.findall(rule)
        raw_operators = RE_GET_OPERATORS.split(rule)
        operators = [operator for operator in raw_operators if operator]
                
        current_app.logger.log(2,f'field_names: {field_names}')
        current_app.logger.log(2,f'operators: {operators}')

        
        # check operators
        for i, operator in enumerate(operators):
            if operator not in SUPPORTED_COMBINATION_RULES_OPERATORS:
                err_msg += f"Template|combination_rules: not supported operator: {operator}. \n"
        
        # if field in template request
        for field_name in field_names:
            if field_name not in template_req:
                err_msg += f"Template|combination_rules: field name: {field_name} doesn't exist in API request. \n"

        # check number of operator & fields
        if len(field_names) != len(operators) + 1:
            err_msg += f"Template|combination_rules: invalid rule. len(fields) should be == len(operators)+1 : {rule}. \n"
            continue
        if len(operators) < 1:
            err_msg += f"Template|combination_rules: invalid rule. No valid operator in rule: {rule}. \n"
            continue
    
    return err_msg

def check_template_errors(template):
    err_msg = ""
    if "error_code_list" not in template:
        err_msg += f"Template|error_code: service error code list is not provided. \n"
    else:
        if not isinstance(template["error_code_list"],list):
            err_msg += f"Template|error_code: invalid service error code type {type(template['error_code_list'])}. Expect list type. \n"
        else:
            if template["error_code_list"] == []:
                err_msg += f"Template|error_code: service error code list cannot be empty list. \n"
    
    if "user_specified_errors" in template:
        for error_key, error_value in template["user_specified_errors"].items():
            if not isinstance(error_value, list):
                err_msg += f"Template|{error_key}: invalid user specified error code type {type(error_value)}. Expect list type. \n"
            else:
                if error_value == []:
                    # err_msg += f"Template|{error_key}: user specified error code list cannot be empty list. \n"
                    pass
                else:
                    for elem in error_value:
                        if not isinstance(elem, int):
                            err_msg += f"Template|{error_key}: {elem} (type:{type(elem)} in {error_key} is invalid, expect int value. \n"

    return err_msg




def check_template_request(template):
    err_msg = ""
    for key, value in template["request"].items():
        field_type = value["type"]
        current_range = value["range"]

        # # (old) check default value type
        # if value["default_value"] != None and not is_correct_type(value["default_value"],field_type):
        #     err_msg += f'[default value] {key} should be {field_type} rather than {type(value["default_value"])}. \n'
        
        if "skip_checking" in value and value["skip_checking"] == True:
            continue
        else:
            # check allow_empty
            if type(value["allow_empty"]) is not bool:
                err_msg += f'[allow_empty] {key} should be boolean. \n'
            # check is_required
            if type(value["is_required"]) is not bool:
                err_msg += f'[is_required] {key} should be boolean. \n'
            # check use_unique_value
            if "use_unique_value" in value and value["use_unique_value"] == True:
                if value["type"] not in CAN_USE_UNIQUE_TYPE:
                    err_msg += f'[use_unique] {key} (type: {value["type"]}) cannot set unique to True. \n'
                if value["type"] in CAN_USE_UNIQUE_TYPE and value["range_type"] not in ["RANGE","NONE"]:
                    err_msg += f'[use_unique] {key} (type: {value["type"]}) range type should be RANGE rather than {value["range_type"]}. \n'
            # check range type
            if "range_type" in value:
                if value["range_type"] not in RANGE_TYPE:
                    err_msg += f'[range_type] {key} (type={value["range_type"]}) is not supported. \n'
                # check range
                if value["range_type"] == "NONE":
                    pass
                if value["range_type"] == "ENUM":
                    for item in current_range:
                        if not is_correct_type(item,field_type):
                            err_msg += f'[range_type] {key} (type={field_type}) has wrong type value {item} ({type(item)}) in ENUM. \n'
                if value["range_type"] == "RANGE":
                    err_msg += _range_check(key, field_type, current_range)
            else:  # if no range_type, we treat it as RANGE
                err_msg += _range_check(key, field_type, current_range)
    return err_msg

def check_template(template):
    '''
    args:
        template: cmd body
    get from func default_template or its children

    return :
        errmsg: None
    for success, otherwise useful info to show to users
    Check points:
        json format
        if key exists in request/response
        if the type of default_value, is_required, allow_empty, range,
    '''
    if type(template) is not dict:
        if type(template) is str:
            template = json.loads(template)
    err_msg = ""
    template = copy.deepcopy(template)
    # convert range value from string to number
    for key, value in template["request"].items():
        value["range"], msg = convert_str_list_to_number_list(value["type"], value["range_type"], value["range"])
        err_msg += msg

    if err_msg:
        current_app.logger.error(f'check template:\n{err_msg}')
        return err_msg
        
    # check combination rules
    err_msg += check_combination_rules(template)
    
    # check default request
    err_msg += check_default_request(template)

    # check template request fields
    err_msg += check_template_request(template)

    # check template user specified errors
    if "user_specified_errors" in template:
        for key, value in template["user_specified_errors"].items():
            for i, item in enumerate(value):
                try:
                    r_item = int(item)
                except Exception:
                    r_item = item
                value[i] = r_item
            template["user_specified_errors"][key] = value
    err_msg += check_template_errors(template)

    # TODO
    # check response
    # check error_code_list

    if err_msg == '':
        return None
    else:
        current_app.logger.error(f'check template:\n{err_msg}')
        return err_msg

def convert_number_to_str(num):
    if num == None:
        return num
    elif isinstance(num,numbers.Number):
        return str(num)
    else:
        current_app.logger.warning(f"Will not convert {num} to str, fallback to None")
        return None

def convert_str_list_to_number_list(field_type,range_type,str_list):
    err_msg = ''
    res = []
    for item in str_list:
        value, msg = convert_str_to_number(field_type,range_type, item)
        err_msg += msg
        res.append(value)
    return res, err_msg

def convert_str_to_number(field_type,range_type,field_value):
    err_msg = ''
    if field_value == None:
        return None,err_msg
    elif  field_type in INT_TYPE or (field_type in STRING_TYPE+["LIST"] and range_type =="RANGE"):
        try:
            field_value = int(field_value)
        except:
            err_msg += f'{field_value} should be integer. \n'
    elif field_type in FLOAT_TYPE:
        try:
            field_value = float(field_value)
        except:
            err_msg += f'{field_value} should be float/double. \n'
    return field_value, err_msg

def _range_check(key_name, field_type, current_range):
    err_msg = ""
    if field_type in ["INT32", "UINT32", "INT64", "UINT64", "DOUBLE", "FLOAT","STRING","BYTES","LIST"]:
        field_range = get_type_range(field_type)
        if len(current_range) != 2:
            err_msg += f'[range] {key_name} should be two numbers. \n'
        elif current_range[0]!=None and not isinstance(current_range[0],numbers.Number):
            err_msg += f'[range] {key_name} left range {current_range[0]} should be number rather than {type(current_range[0])}. \n'
        elif current_range[1]!=None and not isinstance(current_range[1],numbers.Number):
            err_msg += f'[range] {key_name} right range {current_range[1]} should be number rather than {type(current_range[1])}. \n'
        else:
            if field_range[0]!=None and current_range[0]!=None and current_range[0] < field_range[0]:
                err_msg += f'[range] {key_name} left range {current_range[0]} should be greater or equal to MinOf{field_type} {field_range[0]}. \n'
            if field_range[1]!=None and current_range[1]!=None and current_range[1] > field_range[1]:
                err_msg += f'[range] {key_name} right range {current_range[1]} should be less or equal to MaxOf{field_type} {field_range[1]}. \n'
            if current_range[0]!=None and current_range[1]!=None and current_range[0] > current_range[1]:
                err_msg += f'[range] {key_name} left range [{current_range[0]}] should be less or equal to right range [{current_range[1]}]. \n'
            
    elif field_type == "BOOL":
        if len(current_range) != 2:
            err_msg += f'[range] {key_name} should be True and False. \n'
        else:
            if type(current_range[0]) is not bool:
                err_msg += f'[range] {key_name} left range {current_range[0]} should be True or False. \n'
            if type(current_range[1]) is not bool:
                err_msg += f'[range] {key_name} right range {current_range[1]} should be True or False. \n'
    elif field_type in ["DICT","RECURSIVE"]:
        err_msg += f'[range] {key_name} (type={field_type}) range type cannot be RANGE. \n'
    else:
        err_msg += f'[type] {key_name} (type={field_type}) is not supported. \n'
    return err_msg

def get_default_request(req):
    default_request = {}
    for key, value in req.items():
        if value['default_value'] == None or value['default_value'] == "":
            continue
        if "." in key:
            name_list = key.split(".")
            temp = default_request
            for name in name_list[:-1]:
                if '[' in name:
                    list_name = name.split('[')[0]
                    if list_name not in temp:
                        temp[list_name] = [{}]
                    temp = temp[list_name][0]
                elif name not in temp:
                    temp[name] = {}
                    temp = temp[name]
                else:
                    temp = temp[name]
            last_key = name_list[-1]
            if '[' in last_key:
                list_name = last_key.split('[')[0]
                list_index = int(last_key.split('[')[1].split(']')[0])
                if value["type"] == "DICT":
                    if list_name not in temp:
                        temp[list_name] = [{}]
                elif value["type"] == "LIST":
                    if list_name not in temp:
                        temp[list_name] = [[]]
                elif list_name not in temp:
                    temp[list_name] = [0] * (list_index + 1)
                    temp[list_name][list_index] = value["default_value"]
            else:
                last_key = name_list[-1]
                if value["type"] == "DICT":
                    if last_key not in temp:
                        temp[last_key] = {}
                elif value["type"] == "LIST":
                    if last_key not in temp:
                        temp[last_key] = []
                elif last_key not in temp:
                    temp[last_key] = value["default_value"]

        elif "[" in key:
            name_list = key.split("[")
            name = name_list[0]
            index = int(name_list[1].split("]")[0])
            if name not in default_request:
                default_request[name] = []
            if value['type'] != "DICT":
                default_request[name].append(value["default_value"])
        else:
            if value["type"] == "DICT":
                if key not in default_request:
                    default_request[key] = {}
                else:
                    continue
            elif value["type"] == "LIST":
                if key not in default_request:
                    default_request[key] = []
                else:
                    continue
            else:
                default_request[key] = value["default_value"]
    current_app.logger.log(5,f'default request:\n{json.dumps(default_request,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
    return default_request


def set_key(req, path, value):
    
    req = json_update(req, path,value)
    return req
    
    # print(f"set key: {path} from {req}")
    # print(f'--- preview={path.split(".")[:-1]}')
    # pointer = req
    # for key in path.split(".")[:-1]:
    #     if "[" in key:
    #         list_name = key.split("[")[0]
    #         list_index = int(key.split("[")[1].split("]")[0])
    #         if list_name not in pointer:
    #             pointer[list_name] = [{}]
    #         if len(pointer[list_name]) > list_index:
    #             pointer = pointer[list_name][list_index]
    #     elif key not in pointer:
    #         pointer[key] = {}
    #         pointer = pointer[key]
    #     else:
    #         pointer = pointer[key]
    # last_key = path.split(".")[-1]
    # if "[" in last_key:
    #     list_name = last_key.split("[")[0]
    #     list_index = int(last_key.split("[")[1].split("]")[0])
    #     if list_name not in pointer:
    #         pointer[list_name] = [0 * (list_index + 1)]
    #     if len(pointer[list_name]) > list_index:
    #         pointer[list_name][list_index] = value
    # else:
    #     pointer[last_key] = value
    # return req


def del_key(req, path):
    match = json_find(req, path)
    if match:
        req = json_remove(req, path)
    return req

    # # print(f"del key: {path} from {req}")
    # # print(f'--- preview={path.split(".")[:-1]}')
    # match = json_find(req, path)
    # if len(match) < 1:
    #     return req

    # pointer = req
    # for key in path.split(".")[:-1]:
    #     if "[" in key:
    #         list_name = key.split("[")[0]
    #         list_index = int(key.split("[")[1].split("]")[0])
    #         if list_name not in pointer:
    #             return f"{path} doesn't exist"
    #         if len(pointer[list_name]) > list_index:
    #             pointer = pointer[list_name][list_index]
    #     elif key not in pointer:
    #         return f"{path} doesn't exist"
    #     else:
    #         pointer = pointer[key]
    # last_key = path.split(".")[-1]
    # if "[" in last_key:
    #     list_name = last_key.split("[")[0]
    #     list_index = int(last_key.split("[")[1].split("]")[0])
    #     if list_name in pointer:
    #         if len(pointer[list_name]) > list_index:
    #             pointer[list_name].pop(list_index)
    # else:
    #     pointer.pop(last_key, None)
    # return req


def gen_wrong_type_cases(default_req, key, value, error_code_list,unique_attribute={}):
    cases = []
    case_type = "Type Check"
    base_case = {
        "name": "wrong_type_base_case",
        "type": case_type,
        "is_customized_error": True,
        "request": {},
        "response": {},
        "error_code": error_code_list["spex_error"]
    }
    type = value['type']
    type_list = ["STRING", "NUMBER", "BOOL", "DICT", "LIST", "BYTES"]
    if type in NUMBER_TYPE:
        type = "NUMBER"
    type_list.remove(type)
    # bcz in json, bytes are encoded to base64 string
    # so from json POV, these two are the same as string type
    # AND bcz python splib cast number<-->bool, we ignore these cases
    if type == "STRING":
        type_list.remove("BYTES")
    if type == "BYTES":
        type_list.remove("STRING")
    if type == "NUMBER":
        type_list.remove("BOOL")
    if type == "BOOL":
        type_list.remove("NUMBER")
    for cur_type in type_list:
        req = add_unique_fields(default_req,unique_attribute)
        set_key(req, key, get_wrong_type_value(cur_type))
        case = copy.deepcopy(base_case)
        case["name"] = gen_case_name(key,case_type,type,f"set_value_to_{cur_type}")
        case["request"] = req
        cases.append(case)
    return cases

def json_find(json_input,path):
    return jsonpath_ng.parse(f'$.{path}').find(json_input)

def json_update(json_input,path,value):
    return jsonpath_ng.parse(f'$.{path}').update_or_create(json_input,value)

def json_remove(json_input,path):
    return jsonpath_ng.parse(f'$.{path}').filter(lambda x:True, json_input)
    

def get_default_value(req,path,field_type):
    match = json_find(req,path)
    if len(match) > 1:
        current_app.logger.warning(f"Path: {path} has multiple match in request: {req}")
    target_value = match[0].value if match else get_type_default_value(field_type)
    return target_value

def add_unique_fields(base_req,unique_attribute):
    req = copy.deepcopy(base_req)
    if unique_attribute and "fields" in unique_attribute and len(unique_attribute["fields"])>0:
        for field, field_type, field_range_type, field_range in unique_attribute["fields"]:
            set_key(req,field,get_unique_value(field_type,field_range,unique_attribute["count"],field_range_type))
        unique_attribute["count"] += 1
    return req

def get_unique_value(field_type, field_range=[], suffix="", skip_range=False):
    if field_type in STRING_TYPE:
        current = str(int(time.time()*1000000))
        res = f"random_{current}"
        if suffix:
            res = f"{res}_{suffix}"
        if field_type == "BYTES":
            res = base64.b64decode(res)
        if not skip_range or skip_range == "RANGE":
            if field_range and len(field_range) == 2 and field_range[1] and int(field_range[1]) >= 0:
                if len(res) > int(field_range[1]):
                    res = res[len(res) - int(field_range[1]):]
        return res
        
    elif field_type in NUMBER_TYPE:
        left = 0
        right = 2**31 -1
        if not skip_range or skip_range == "RANGE":
            if field_range and len(field_range) == 2:
                if field_range[0]:
                    left = int(float(field_range[0]))
                if field_range[1]:
                    right = int(float(field_range[1]))
        case_count_offset = 20000
        right -= case_count_offset
        if left > right:
            left, right = right, left
        res = random.randint(left,right)
        if suffix and (type(suffix) == int or type(suffix) == float or str.isnumeric(suffix)):
            res += int(suffix)
        return res
        
    else:
        raise Exception(f"Not supported unique field type: {field_type}")
        
## TODO
def get_combination_value():
    pass
## to generate combination rules cases, currently support &&,||
## don't support (),
## fieldA.subA && fieldA.subB
def gen_combination_rules_cases(customized_template, error_code_list,unique_attribute={}):
    cases = []
    case_type = "Combination Check"
    default_req = json.loads(customized_template["default_request"])
    template_req = customized_template["request"]
    rules = customized_template["combination_rules"]
    is_customized_error = "combination_error" in error_code_list and error_code_list["combination_error"] != []
    target_errors = error_code_list["combination_error"] if is_customized_error else error_code_list["service_error"]
    # re_remove_space = re.compile(r'\s')
    # re_get_field_names = re.compile(r'([\w\.\[\]]+)')
    # re_get_field_names = re.compile(r'\{\{(.+?)\}\}')
    # re_get_operators = re.compile(r'(&&|\|\|)')
    # re_get_operators = re.compile(r'\{\{.*?\}\}')

    base_case = {
        "name": "combination_base_case",
        "type": case_type,
        "is_customized_error": True,
        "request": {},
        "response": {},
        "error_code": error_code_list["success"]
    }

    for rule in rules:
        if not rule:
            continue
        rule = RE_REMOVE_SPACE.sub("", rule)
        field_names = RE_GET_FIELD_NAMES.findall(rule)
        raw_operators = RE_GET_OPERATORS.split(rule)
        operators = [operator for operator in raw_operators if operator]

        # base_req = add_unique_fields(default_req,unique_attribute)
        # for field_name in field_names:
        #     del_key(base_req, field_name)
        
        # currently only support all operators are && or ||, combination is not supported now.
        rule_type = operators[0]
        for operator in operators:
            if operator != rule_type:
                rule_type = ""
                break
        
        if rule_type == "||" or rule_type == "or" or rule_type == "OR":
            # Cn_0
            req = add_unique_fields(default_req,unique_attribute)
            for field_name in field_names:
                del_key(req, field_name)
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name("",case_type,rule,f"Cn_0: All fields NOT in request")
            case["request"] = req
            case["is_customized_error"] = is_customized_error
            case["error_code"] = target_errors
            cases.append(case)
            # Cn_n
            req = add_unique_fields(default_req,unique_attribute)
            for field_name in field_names:
                if "use_unique_value" in template_req[field_name] and template_req[field_name]["use_unique_value"]:
                    target_value = get_unique_value(template_req[field_name]["type"],template_req[field_name]["range"],unique_attribute["count"],template_req[field_name]["range_type"])
                else:
                    target_value = get_default_value(default_req,field_name,template_req[field_name]["type"])
                set_key(req,field_name, target_value)
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name("",case_type,rule,f"Cn_n: All fields in request")
            case["request"] = req
            cases.append(case)
            # Cn_1
            for field_name in field_names:
                req = add_unique_fields(default_req,unique_attribute)
                for field_name in field_names:
                    del_key(req, field_name)
                if "use_unique_value" in template_req[field_name] and template_req[field_name]["use_unique_value"]:
                    target_value = get_unique_value(template_req[field_name]["type"],template_req[field_name]["range"],unique_attribute["count"],template_req[field_name]["range_type"])
                else:
                    target_value = get_default_value(default_req,field_name,template_req[field_name]["type"])
                set_key(req,field_name, target_value)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name("",case_type,rule,f"Cn_1: one field in request: {field_name}")
                case["request"] = req
                cases.append(case)

        elif rule_type == "&&" or rule_type == "and" or rule_type == "AND":
            # Cn_0
            req = add_unique_fields(default_req,unique_attribute)
            for field_name in field_names:
                del_key(req, field_name)
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name("",case_type,rule,f"Cn_0: All fields NOT in request")
            case["request"] = req
            case["is_customized_error"] = is_customized_error
            case["error_code"] = target_errors
            cases.append(case)
            # Cn_n
            req = add_unique_fields(default_req,unique_attribute)
            for field_name in field_names:
                if "use_unique_value" in template_req[field_name] and template_req[field_name]["use_unique_value"]:
                    target_value = get_unique_value(template_req[field_name]["type"],template_req[field_name]["range"],unique_attribute["count"],template_req[field_name]["range_type"])
                else:
                    target_value = get_default_value(default_req,field_name,template_req[field_name]["type"])
                set_key(req,field_name, target_value)
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name("",case_type,rule,f"Cn_n: All fields in request")
            case["request"] = req
            cases.append(case)
            # Cn_1
            for field_name in field_names:
                req = add_unique_fields(default_req,unique_attribute)
                for field_name in field_names:
                    del_key(req, field_name)
                if "use_unique_value" in template_req[field_name] and template_req[field_name]["use_unique_value"]:
                    target_value = get_unique_value(template_req[field_name]["type"],template_req[field_name]["range"],unique_attribute["count"],template_req[field_name]["range_type"])
                else:
                    target_value = get_default_value(default_req,field_name,template_req[field_name]["type"])
                set_key(req,field_name, target_value)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name("",case_type,rule,f"Cn_1: one field in request: {field_name}")
                case["request"] = req
                case["is_customized_error"] = is_customized_error
                case["error_code"] = target_errors
                cases.append(case)

        # eval_dict_val = {field_name:get_combination_value(field_name) for field_name in field_names}
        # while not eval(rule, eval_dict_val):
        #     pass
    return cases

def gen_is_required_cases(default_req, key, value, error_code_list,unique_attribute={}):
    cases = []
    case_type = "Required Check"
    is_customized_error = "required_error" in error_code_list and error_code_list["required_error"] != []
    target_errors = error_code_list["required_error"] if is_customized_error else error_code_list["service_error"]
    base_case = {
        "name": "required_base_case",
        "type": case_type,
        "is_customized_error": True,
        "request": {},
        "response": {},
        "error_code": error_code_list["success"]
    }
    if value["is_required"] == True:
        # field not passed
        req = add_unique_fields(default_req,unique_attribute)
        del_key(req, key)
        case = copy.deepcopy(base_case)
        case["name"] = gen_case_name(key,case_type,"TRUE",f"{key}_NOT_in_req")
        case["request"] = req
        case["is_customized_error"] = is_customized_error
        case["error_code"] = target_errors
        cases.append(case)
        # # field value is null
        # set_key(req, key, None)
        # case = copy.deepcopy(base_case)
        # case["name"] = gen_case_name(key,case_type,"TRUE",f"{key}_is_NULL")
        # case["request"] = req
        # case["is_customized_error"] = is_customized_error
        # case["error_code"] = target_errors
        # cases.append(case)

        if value['type'] not in ["LIST", "DICT"]:
            # field passed
            req = add_unique_fields(default_req,unique_attribute)
            case = copy.deepcopy(base_case)
            # target_value = value["default_value"] if "default_value" in value and value["default_value"]!=None else get_type_default_value(value["type"])
            if "use_unique_value" in value and not value["use_unique_value"]:
                target_value = get_default_value(req,key,value["type"])
            case["name"] = gen_case_name(key,case_type,"TRUE",f"{key}_in_req")
            case["request"] = req
            cases.append(case)
    else:
        # # field is NULL
        # set_key(req, key, None)
        # case = copy.deepcopy(base_case)
        # case["name"] = gen_case_name(key,case_type,"FALSE",f"{key}_is_NULL")
        # case["request"] = req
        # cases.append(case)
        # field is not passed
        req = add_unique_fields(default_req,unique_attribute)
        del_key(req, key)
        case = copy.deepcopy(base_case)
        case["name"] = gen_case_name(key,case_type,"FALSE",f"{key}_NOT_in_req")
        case["request"] = req
        cases.append(case)

        if value['type'] not in ["LIST", "DICT"]:
            # field passed
            req = add_unique_fields(default_req,unique_attribute)
            # target_value = value["default_value"] if "default_value" in value and value["default_value"]!=None else get_type_default_value(value["type"])
            if "use_unique_value" in value and not value["use_unique_value"]:
                target_value = get_default_value(req,key,value["type"])
                set_key(req, key, target_value)
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name(key,case_type,"FALSE",f"{key}_in_req")
            case["request"] = req
            cases.append(case)
    return cases


def gen_allow_empty_cases(default_req, key, value, error_code_list,unique_attribute={}):
    cases = []
    case_type = "Empty Check"
    is_customized_error = "empty_error" in error_code_list and error_code_list["empty_error"] != []
    target_errors = error_code_list["empty_error"] if is_customized_error else error_code_list["service_error"]
    base_case = {
        "name": "empty_base_case",
        "type": case_type,
        "is_customized_error": True,
        "request": {},
        "response": {},
        "error_code": error_code_list["success"]
    }
    if value["type"] != "BOOL":
        if value["allow_empty"] == True:
            # field is empty
            req = add_unique_fields(default_req,unique_attribute)
            set_key(req, key, get_empty_value(value["type"]))
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name(key,case_type,"TRUE",f"{key}_set_to_empty_value")
            case["request"] = req
            cases.append(case)
            if value['type'] not in ["LIST", "DICT"]:
                # field is not empty
                req = add_unique_fields(default_req,unique_attribute)
                # target_value = value["default_value"] if "default_value" in value and value["default_value"]!=None else get_type_default_value(value["type"])
                if "use_unique_value" in value and not value["use_unique_value"]:
                    target_value = get_default_value(req,key,value["type"])
                    set_key(req, key, target_value)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,"TRUE",f"{key}_set_to_NOT_empty_value")
                case["request"] = req
                cases.append(case)
        else:
            # field is empty
            req = add_unique_fields(default_req,unique_attribute)
            set_key(req, key, get_empty_value(value["type"]))
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name(key,case_type,"FALSE",f"{key}_set_to_empty_value")
            case["request"] = req
            case["is_customized_error"] = is_customized_error
            case["error_code"] = target_errors
            cases.append(case)
            if value['type'] not in ["LIST", "DICT"]:
                # field is not empty
                req = add_unique_fields(default_req,unique_attribute)
                # target_value = value["default_value"] if "default_value" in value and value["default_value"]!=None else get_type_default_value(value["type"])
                if "use_unique_value" in value and not value["use_unique_value"]:
                    target_value = get_default_value(req,key,value["type"])
                    set_key(req, key, target_value)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,"FALSE",f"{key}_set_to_not_empty_value")
                case["request"] = req
                cases.append(case)
    return cases


def gen_type_range_cases(default_req, key, value, error_code_list,unique_attribute={},template=""):
    cases = []
    case_type = "Range Check"
    is_customized_error = "boundary_error" in error_code_list and error_code_list["boundary_error"] != []
    target_errors = error_code_list["boundary_error"] if is_customized_error else error_code_list["service_error"]
    base_case = {
        "name": "boundary_base_case",
        "type": case_type,
        "is_customized_error": True,
        "request": {},
        "response": {},
        "error_code": error_code_list["success"]
    }
    # skip range case for dict
    if value["type"] in ["DICT"]:
        return []

    range_type = value["range_type"] if "range_type" in value else ""
    if range_type == "":
        range_type = "RANGE"
    range_type = range_type.upper()

    if range_type == "NONE":
        return []

    elif range_type == "ENUM":
        if value["type"] in ["LIST","DICT"]:
            return []
        # case_type = "range_enum"
        base_case["type"] = case_type
        is_customized_error = "enum_error" in error_code_list and error_code_list["enum_error"] != []
        target_errors = error_code_list["enum_error"] if is_customized_error else error_code_list["service_error"]
        enum_list = value["range"] if "range" in value else []
        if not isinstance(enum_list, list) or enum_list == []:
            current_app.logger.warning(f"wrong enum range for {key}")
            return []
        # gen cases for all enum
        # avoid generating too many enum cases
        if len(enum_list) > 100:
            current_app.logger.warning(f"Too many enum items for {key}. Use 1st - 100th only.")
            enum_list = enum_list[:101]
        enum_list.sort()
        for enum in enum_list:
            req = add_unique_fields(default_req,unique_attribute)
            set_key(req, key, enum)
            case = copy.deepcopy(base_case)
            case["name"] = gen_case_name(key,case_type,value['type'],f"within_enum__set_to_{enum}")
            case["request"] = req
            cases.append(case)
        # gen case that is out of enum
        if value["type"] == "BOOL":
            pass
        elif value["type"] == "STRING":
            v = get_type_default_value(value["type"])
            req = add_unique_fields(default_req,unique_attribute)
            if v not in enum_list:
                set_key(req, key, v)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,value['type'],f"out_of_enum__set_to_{v}")
                case["request"] = req
                case["is_customized_error"] = is_customized_error
                case["error_code"] = target_errors
                cases.append(case)
            elif v*2 not in enum_list:
                set_key(req, key, v*2)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,value['type'],f"out_of_enum__set_to_{v*2}")
                case["request"] = req
                case["is_customized_error"] = is_customized_error
                case["error_code"] = target_errors
                cases.append(case)
            elif v*4 not in enum_list:
                set_key(req, key, v*4)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,value['type'],f"out_of_enum__set_to_{v*4}")
                case["request"] = req
                case["is_customized_error"] = is_customized_error
                case["error_code"] = target_errors
                cases.append(case)
        elif value["type"] in NUMBER_TYPE:
            if enum_list[0]-1 >= get_type_range(value["type"])[0]:
                req = add_unique_fields(default_req,unique_attribute)
                set_key(req, key, enum_list[0]-1)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,value['type'],f"out_of_enum__set_to_{enum_list[0]-1}")
                case["request"] = req
                case["is_customized_error"] = is_customized_error
                case["error_code"] = target_errors
                cases.append(case)
            if enum_list[-1]+1 <= get_type_range(value["type"])[1]:
                req = add_unique_fields(default_req,unique_attribute)
                set_key(req, key, enum_list[-1]+1)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,value['type'],f"out_of_enum__set_to_{enum_list[-1]+1}")
                case["request"] = req
                case["is_customized_error"] = is_customized_error
                case["error_code"] = target_errors
                cases.append(case)
            
    elif range_type == "RANGE":
        if "range" in value and len(value["range"]) == 2:
            field_range = value["range"]
            offset = 1

            if value["type"] == "BOOL":
                # case_type = "range_of_bool"
                base_case["type"] = case_type
                # set bool field to True
                req = add_unique_fields(default_req,unique_attribute)
                set_key(req, key, True)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,value['type'],"set_to_True")
                case["request"] = req
                cases.append(case)
                # set bool field to False
                req = add_unique_fields(default_req,unique_attribute)
                set_key(req, key, False)
                case = copy.deepcopy(base_case)
                case["name"] = gen_case_name(key,case_type,value['type'],"set_to_False")
                case["request"] = req
                cases.append(case)

            ## range of string is actually length of string
            elif value["type"] == "STRING":
                # case_type = "range_of_string_length"
                base_case["type"] = case_type
                if isinstance(field_range[0], numbers.Number):
                    # set string length field to left boundary
                    req = add_unique_fields(default_req,unique_attribute)
                    length = field_range[0]
                    if "use_unique_value" in value and not value["use_unique_value"]:
                        set_key(req, key, "a" * length)
                    else:
                        # uniq_str = json_find(req,key)[-length:]
                        match = json_find(req,key)
                        uniq_str = match[0].value[-length:]
                        if len(uniq_str) >= length:
                            set_key(req, key, uniq_str)
                        else:
                            uniq_str = uniq_str + "a" * (length - len(uniq_str))
                    case = copy.deepcopy(base_case)
                    case["name"] = gen_case_name(key,case_type,value['type'],"set_to_on_left_boundary")
                    case["request"] = req
                    cases.append(case)
                    # set string length field in left boundary
                    if isinstance(field_range[1], numbers.Number):
                        if field_range[0]+offset < field_range[1]:
                            req = add_unique_fields(default_req,unique_attribute)
                            length = field_range[0]+offset
                            if "use_unique_value" in value and not value["use_unique_value"]:
                                set_key(req, key, "a" * length)
                            else:
                                # uniq_str = json_find(req,key)[-length:]
                                match = json_find(req,key)
                                uniq_str = match[0].value[-length:]
                                if len(uniq_str) >= length:
                                    set_key(req, key, uniq_str)
                                else:
                                    uniq_str = uniq_str + "a" * (length - len(uniq_str))
                            case = copy.deepcopy(base_case)
                            case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_left_boundary"),
                            case["request"] = req
                            cases.append(case)
                        else:
                            current_app.logger.debug(f"{key} value of in range [{field_range[0]+offset}] out of right bound of [{field_range[1]}]")
                    else:
                        req = add_unique_fields(default_req,unique_attribute)
                        length = field_range[0]+offset
                        if "use_unique_value" in value and not value["use_unique_value"]:
                            set_key(req, key, "a" * length)
                        else:
                            # uniq_str = json_find(req,key)[-length:]
                            match = json_find(req,key)
                            uniq_str = match[0].value[-length:]
                            if len(uniq_str) >= length:
                                set_key(req, key, uniq_str)
                            else:
                                uniq_str = uniq_str + "a" * (length - len(uniq_str))
                        case = copy.deepcopy(base_case)
                        case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_left_boundary")
                        case["request"] = req
                        cases.append(case)
                    # set string length field out of left boundary
                    if field_range[0] - 1 >= 0:
                        req = add_unique_fields(default_req,unique_attribute)
                        length = field_range[0] - 1
                        if "use_unique_value" in value and not value["use_unique_value"]:
                            set_key(req, key, "a" * length)
                        else:
                            # uniq_str = json_find(req,key)[-length:]
                            match = json_find(req,key)
                            uniq_str = match[0].value[-length:]
                            if len(uniq_str) >= length:
                                set_key(req, key, uniq_str)
                            else:
                                uniq_str = uniq_str + "a" * (length - len(uniq_str))
                        case = copy.deepcopy(base_case)
                        case["name"] = gen_case_name(key,case_type,value['type'],"set_to_out_of_left_boundary")
                        case["request"] = req
                        case["is_customized_error"] = is_customized_error
                        case["error_code"] = target_errors
                        cases.append(case)
                else:
                    current_app.logger.warning(f"{key} doesn't have valid left range [{field_range[0]}](type={type(field_range[0])})")

                if isinstance(field_range[1], numbers.Number):
                    # set string length field to right boundary
                    req = add_unique_fields(default_req,unique_attribute)
                    length = field_range[1]
                    if "use_unique_value" in value and not value["use_unique_value"]:
                        set_key(req, key, "a" * length)
                    else:
                        # uniq_str = json_find(req,key)[-length:]
                        match = json_find(req,key)
                        uniq_str = match[0].value[-length:]
                        if len(uniq_str) >= length:
                            set_key(req, key, uniq_str)
                        else:
                            uniq_str = uniq_str + "a" * (length - len(uniq_str))
                    case = copy.deepcopy(base_case)
                    case["name"] = gen_case_name(key,case_type,value['type'],"set_to_on_right_boundary")
                    case["request"] = req
                    cases.append(case)
                    # set string length field in right boundary
                    if isinstance(field_range[0], numbers.Number):
                        if field_range[1]-offset > field_range[0]:
                            req = add_unique_fields(default_req,unique_attribute)
                            length = field_range[1]-offset
                            if "use_unique_value" in value and not value["use_unique_value"]:
                                set_key(req, key, "a" * length)
                            else:
                                # uniq_str = json_find(req,key)[-length:]
                                match = json_find(req,key)
                                uniq_str = match[0].value[-length:]
                                if len(uniq_str) >= length:
                                    set_key(req, key, uniq_str)
                                else:
                                    uniq_str = uniq_str + "a" * (length - len(uniq_str))
                            case = copy.deepcopy(base_case)
                            case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_right_boundary")
                            case["request"] = req
                            cases.append(case)
                        else:
                            current_app.logger.debug(f"{key} value of in range [{field_range[1]-offset}] out of left bound of [{field_range[0]}]")
                    else:
                        req = add_unique_fields(default_req,unique_attribute)
                        length = field_range[1]
                        if "use_unique_value" in value and not value["use_unique_value"]:
                            set_key(req, key, "a" * length)
                        else:
                            # uniq_str = json_find(req,key)[-length:]
                            match = json_find(req,key)
                            uniq_str = match[0].value[-length:]
                            if len(uniq_str) >= length:
                                set_key(req, key, uniq_str)
                            else:
                                uniq_str = uniq_str + "a" * (length - len(uniq_str))
                        case = copy.deepcopy(base_case)
                        case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_right_boundary")
                        case["request"] = req
                        cases.append(case)
                    # set string length field out of left boundary
                    req = add_unique_fields(default_req,unique_attribute)
                    length = field_range[1] + 1
                    if "use_unique_value" in value and not value["use_unique_value"]:
                        set_key(req, key, "a" * length)
                    else:
                        # uniq_str = json_find(req,key)[-length:]
                        match = json_find(req,key)
                        uniq_str = match[0].value[-length:]
                        if len(uniq_str) >= length:
                            set_key(req, key, uniq_str)
                        else:
                            uniq_str = uniq_str + "a" * (length - len(uniq_str))
                    case = copy.deepcopy(base_case)
                    case["name"] = gen_case_name(key,case_type,value['type'],"set_to_out_of_right_boundary"),
                    case["request"] = req
                    case["is_customized_error"] = is_customized_error
                    case["error_code"] = target_errors
                    cases.append(case)
                else:
                    current_app.logger.warning(f"{key} doesn't have valid right range [{field_range[1]}](type={type(field_range[1])})")

            elif value["type"] in NUMBER_TYPE:
                # case_type = "range_of_number_value"
                base_case["type"] = case_type
                if value["type"] in ["FLOAT","DOUBLE"]:
                    offset = 0.1

                ## left boundary
                if isinstance(field_range[0], numbers.Number):
                # out_of_left_boundary
                    type_left_range = get_type_range(value["type"])[0]
                    req = add_unique_fields(default_req,unique_attribute)
                    set_key(req, key, field_range[0] - 1)
                    case = copy.deepcopy(base_case)
                    case["name"] = gen_case_name(key,case_type,value['type'],"set_to_out_of_left_boundary")
                    case["request"] = req
                    if field_range[0] > type_left_range:
                        case["is_customized_error"] = is_customized_error
                        case["error_code"] = target_errors
                    else:
                        case["error_code"] = error_code_list["spex_error"]
                    cases.append(case)
                    # on_left_boundary
                    req = add_unique_fields(default_req,unique_attribute)
                    set_key(req, key, field_range[0])
                    case = copy.deepcopy(base_case)
                    case["name"] = gen_case_name(key,case_type,value['type'],"set_to_on_left_boundary")
                    case["request"] = req
                    cases.append(case)
                    # in_left_boundary
                    if isinstance(field_range[1], numbers.Number):
                        if field_range[0]+offset < field_range[1]:
                            req = add_unique_fields(default_req,unique_attribute)
                            set_key(req, key, field_range[0]+offset)
                            case = copy.deepcopy(base_case)
                            case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_left_boundary")
                            case["request"] = req
                            cases.append(case)
                        else:
                            current_app.logger.debug(f"{key} value of in range [{field_range[0]+offset}] out of right bound of [{field_range[1]}]")
                    else:
                        req = add_unique_fields(default_req,unique_attribute)
                        set_key(req, key, field_range[0]+offset)
                        case = copy.deepcopy(base_case)
                        case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_left_boundary")
                        case["request"] = req
                        cases.append(case)
                else:
                    current_app.logger.warning(f"{key} doesn't have valid left range [{field_range[0]}](type={type(field_range[0])})")

                ## right boundary
                if isinstance(field_range[1], numbers.Number):
                    # out_of_right_boundary
                    type_right_range = get_type_range(value["type"])[1]
                    req = add_unique_fields(default_req,unique_attribute)
                    set_key(req, key, field_range[1] + 1)
                    case = copy.deepcopy(base_case)
                    case["name"] = gen_case_name(key,case_type,value['type'],"set_to_out_of_right_boundary")
                    case["request"] = req
                    if field_range[1] < type_right_range:
                        case["is_customized_error"] = is_customized_error
                        case["error_code"] = target_errors
                    else:
                        case["error_code"] = error_code_list["spex_error"]
                    cases.append(case)
                    # on_right_boundary
                    req = add_unique_fields(default_req,unique_attribute)
                    set_key(req, key, field_range[1])
                    case = copy.deepcopy(base_case)
                    case["name"] = gen_case_name(key,case_type,value['type'],"set_to_on_right_boundary"),
                    case["request"] = req
                    cases.append(case)
                    # in_right_boundary
                    if isinstance(field_range[0], numbers.Number):
                        if field_range[1]-offset > field_range[0]:
                            req = add_unique_fields(default_req,unique_attribute)
                            set_key(req, key, field_range[1]-offset)
                            case = copy.deepcopy(base_case)
                            case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_right_boundary")
                            case["request"] = req
                            cases.append(case)
                        else:
                            current_app.logger.debug(f"{key} value of in range [{field_range[1]-offset}] out of left bound of [{field_range[1]}]")
                    else:
                        req = add_unique_fields(default_req,unique_attribute)
                        set_key(req, key, field_range[0])
                        case = copy.deepcopy(base_case)
                        case["name"] = gen_case_name(key,case_type,value['type'],"set_to_in_right_boundary"),
                        case["request"] = req
                        cases.append(case)
                else:
                    current_app.logger.warning(f"{key} doesn't have valid right range [{field_range[1]}](type={type(field_range[1])})")
            elif value["type"] == "LIST":
                if key+"[0]" not in template["request"]:
                    current_app.logger.warning(f"[Range case] Skip generating range case for field[{key}] due to {key}[0] not in template not supported")
                    return []
                else:
                    elem_value = template["request"][key+"[0]"]
                    if elem_value["type"] not in BASIC_TYPE:
                        current_app.logger.warning(f"[Range case] Skip generating range case for field[{key}] due to element type[{elem_value['type']}] not supported")
                        return []
                    else:
                        # case_type = "range_of_list_length"
                        base_case["type"] = case_type
                        if isinstance(field_range[0], numbers.Number):
                            # set list length field to left boundary
                            sample_value = get_default_value(default_req,key+"[0]",elem_value["type"])
                            req = add_unique_fields(default_req,unique_attribute)
                            set_key(req, key, [sample_value] * field_range[0])
                            case = copy.deepcopy(base_case)
                            case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_on_left_boundary")
                            case["request"] = req
                            cases.append(case)
                            # set list length field in left boundary
                            if isinstance(field_range[1], numbers.Number):
                                if field_range[0]+offset < field_range[1]:
                                    req = add_unique_fields(default_req,unique_attribute)
                                    set_key(req, key, [sample_value] * (field_range[0]+offset))
                                    case = copy.deepcopy(base_case)
                                    case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_in_left_boundary"),
                                    case["request"] = req
                                    cases.append(case)
                                else:
                                    current_app.logger.debug(f"{key} value of in range [{field_range[0]+offset}] out of right bound of [{field_range[1]}]")
                            else:
                                req = add_unique_fields(default_req,unique_attribute)
                                set_key(req, key, [sample_value] * (field_range[0]+offset))
                                case = copy.deepcopy(base_case)
                                case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_in_left_boundary")
                                case["request"] = req
                                cases.append(case)
                            # set list length field out of left boundary
                            if field_range[0] - 1 >= 0:
                                req = add_unique_fields(default_req,unique_attribute)
                                set_key(req, key, [sample_value] * (field_range[0] - 1))
                                case = copy.deepcopy(base_case)
                                case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_out_of_left_boundary")
                                case["request"] = req
                                case["is_customized_error"] = is_customized_error
                                case["error_code"] = target_errors
                                cases.append(case)
                        else:
                            current_app.logger.warning(f"{key} doesn't have valid left range [{field_range[0]}](type={type(field_range[0])})")
                        
                        if isinstance(field_range[1], numbers.Number):
                            # set list length field to right boundary
                            sample_value = get_default_value(default_req,key+"[0]",elem_value["type"])
                            req = add_unique_fields(default_req,unique_attribute)
                            set_key(req, key, [sample_value] * field_range[1])
                            case = copy.deepcopy(base_case)
                            case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_on_right_boundary")
                            case["request"] = req
                            cases.append(case)
                            # set list length field in right boundary
                            if isinstance(field_range[0], numbers.Number):
                                if field_range[1]-offset > field_range[0]:
                                    req = add_unique_fields(default_req,unique_attribute)
                                    set_key(req, key, [sample_value] * (field_range[1]-offset))
                                    case = copy.deepcopy(base_case)
                                    case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_in_right_boundary")
                                    case["request"] = req
                                    cases.append(case)
                                else:
                                    current_app.logger.debug(f"{key} value of in range [{field_range[1]-offset}] out of left bound of [{field_range[0]}]")
                            else:
                                req = add_unique_fields(default_req,unique_attribute)
                                set_key(req, key, [sample_value] * field_range[1])
                                case = copy.deepcopy(base_case)
                                case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_in_right_boundary")
                                case["request"] = req
                                cases.append(case)
                            # set list length field out of left boundary
                            req = add_unique_fields(default_req,unique_attribute)
                            set_key(req, key, [sample_value] * (field_range[1] + 1))
                            case = copy.deepcopy(base_case)
                            case["name"] = gen_case_name(key,case_type,value['type'],"set_list_to_out_of_right_boundary"),
                            case["request"] = req
                            case["is_customized_error"] = is_customized_error
                            case["error_code"] = target_errors
                            cases.append(case)
                        else:
                            current_app.logger.warning(f"{key} doesn't have valid right range [{field_range[1]}](type={type(field_range[1])})")

        else:
            current_app.logger.warning(f"{key} doesn't have valid range [{value['range']}]")
            return []
    else:
        current_app.logger.warning(f"Not supported range type {range_type}")

    return cases

def convert_b64str_to_bytes(input,template,prefix=""):
    if isinstance(input, dict):
        for k, v in input.items():
            key_name = f'{prefix}.{k}' if prefix else k
            if template["request"][key_name]["type"] == "BYTES":
                input[k] = base64.b64decode(v)
            elif template["request"][key_name]["type"] == "DICT":
                convert_b64str_to_bytes(input[k],template,key_name)
            elif template["request"][key_name]["type"] == "LIST":
                new_list = convert_b64str_to_bytes(input[k],template,key_name)
                if new_list:
                    input[k] = new_list

    elif isinstance(input, list):
        if template["request"][prefix+"[0]"]["type"] == "BYTES":
            new_list = []
            for elem in input:
                new_list.append(base64.b64decode(elem))
            return new_list
        elif template["request"][prefix+"[0]"]["type"] == "DICT":
            key_name = f'{prefix}[{0}]'
            for elem in input:
                convert_b64str_to_bytes(elem, template, key_name)
        elif template["request"][prefix+"[0]"]["type"] == "LIST":
            key_name = f'{prefix}[{0}]'
            for i, elem in enumerate(input):
                new_list = convert_b64str_to_bytes(elem, template, key_name)
                if new_list:
                    input[i] = new_list

def gen_case_name(key,case_type,value,case_name):
    if case_type == "Empty Check" or case_type == "Required Check":
        res = f"field_name: {key} | case_type: {case_type}({value}) | case: {case_name}"
    elif case_type == "Combination Check":
        res = f"case_type: {case_type} | rule: {value} | case: {case_name}"
    else:
        res = f"field_name: {key} | case_type: {case_type} | field_type: {value} | case: {case_name}"
    return res

def generate_cases(request, response, template):
    '''
    args:
        request: cmd body
        response: cmd body
        template: cmd body
    get from func default_template or its children
    base on allow_empty, is_required, range, type

    return :
        {
            "cases_num":10,
            "cases":{
                "field1": [{
                        "name": "xxxx1",
                        "request": {},
                        "response": {},
                        "error_code": [10002,10003]
                    },
                    {
                        "name": "xxxx2",
                        "request": {},
                        "response": {},
                        "error_code": [10002,10003]
                    }
                ],
                "field2": []
            }
        }
    '''
    request = copy.deepcopy(request)
    response = copy.deepcopy(response)
    template = copy.deepcopy(template)
    unique_attribute = {
        "count": 1,
        "fields": [] # [[key_name, key_type, key_range_type, key_range],[]]
    }
    for key, value in template["request"].items():
        if "use_unique_value" in value and value["use_unique_value"] == True:
            unique_attribute["fields"].append([key,value["type"],value["range_type"],value["range"]])
    result = {
        "cases_num": 0,
        "cases": {}
    }
    error_code_list_SERVICE_ERROR = template["error_code_list"]
    error_code_list_SUCCESS = ERROR_CODE_LIST_SPEX_SUCCESS
    error_code_list_SPEX_ERROR = ERROR_CODE_LIST_SPEX_ERROR

    error_code_list = {
        "service_error": error_code_list_SERVICE_ERROR,
        "spex_error": error_code_list_SPEX_ERROR,
        "success": error_code_list_SUCCESS
    }
    if "user_specified_errors" in template:
        error_code_list.update(template["user_specified_errors"])

    # default_req = get_default_request(template["request"])
    try:
        default_req = json.loads(template["default_request"])
        convert_b64str_to_bytes(default_req,template)

    except json.decoder.JSONDecodeError as err:
        current_app.logger.error(f'[default_request] load json failed:\n original request: {template["default_request"]}. \n err: {err}')
        return {"cases_num":0}

    err_msg = ""
    # convert range value from string to number
    for key, value in template["request"].items():
        value["range"], msg = convert_str_list_to_number_list(value["type"], value["range_type"], value["range"])
        err_msg += msg
    if err_msg:
        current_app.logger.error(f'Error when generating cases: {err_msg}')

    cases_num = 0

    #### default case ####
    default_case_req = add_unique_fields(default_req,unique_attribute)
    result["cases"]["default_request"] = []
    result["cases"]["default_request"].append({
        "error_code":error_code_list["success"],
        "name":"default case | use default request, should pass",
        "type": "Default Case",
        "is_customized_error": True,
        "request":default_case_req,
        "response":{}
    })
    cases_num += 1

    #### combanation rules cases ####
    combination_rules_cases = gen_combination_rules_cases(template, error_code_list,unique_attribute)
    result["cases"]["combination_rules"] = combination_rules_cases
    cases_num += len(combination_rules_cases)

    if 'user_specified_errors' in template and 'parameter_errors' in template['user_specified_errors']:
        if template['user_specified_errors']['parameter_errors']:
            error_code_list["service_error"] = template['user_specified_errors']['parameter_errors']

    for key, value in template["request"].items():
        count = 0
        result["cases"][key] = []
        if value["type"] == "RECURSIVE":
            continue
        if "skip_checking" in value and value["skip_checking"] == True:
            continue
        #### field attribute cases ####
        ## is_required
        is_required_cases = gen_is_required_cases(default_req, key, value, error_code_list,unique_attribute)
        result["cases"][key].extend(is_required_cases)
        count += len(is_required_cases)

        ## allow_empty
        allow_empty_cases = gen_allow_empty_cases(default_req, key, value, error_code_list,unique_attribute)
        result["cases"][key].extend(allow_empty_cases)
        count += len(allow_empty_cases)

        #### field range cases ####
        type_range_cases = gen_type_range_cases(default_req, key, value, error_code_list,unique_attribute,template=template)
        result["cases"][key].extend(type_range_cases)
        count += len(type_range_cases)

        #### field wrong type cases ####
        wrong_type_cases = gen_wrong_type_cases(default_req, key, value, error_code_list,unique_attribute)
        result["cases"][key].extend(wrong_type_cases)
        count += len(wrong_type_cases)

        cases_num += count

    result["cases_num"] = cases_num
    current_app.logger.log(5,f'generated cases:\n{json.dumps(result,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
    return result


def test_convert_b64str_to_bytes():
    default_req = {
        "basic":"YQ==",
        "int":1,
        "string":"YQ==",
        "in_list":["YQ==","YQ=="],
        "string_list":["YQ==","YQ=="],
        "dict_in_list":[{"in_dict_list":"YQ==","string":"YQ==","bytes_list":["YQ==","YQ=="]},
            {"in_dict_list":"YQ==","string":"YQ==","bytes_list":["YQ==","YQ=="]}],
        "list_in_list":[["YQ==","YQ=="],["YQ==","YQ=="]],
        "in_dict":{
            "inside_dict":"YQ==",
            "in_list":["YQ==","YQ=="],
            "dict_in_dict":{
                "inside_of_dict":"YQ==",
            },
            "list_in_list":[["YQ==","YQ=="],["YQ==","YQ=="]],
        }
    }
    template = {
        "request":{
            "basic":{
                "type":"BYTES"
            },
            "int":{
                "type":"INT32"
            },
            "string":{
                "type":"STRING"
            },
            "dict_in_list":{
                "type":"LIST"
            },
            "dict_in_list[0]":{
                "type":"DICT"
            },
            "dict_in_list[0].in_dict_list":{
                "type":"BYTES"
            },
            "dict_in_list[0].string":{
                "type":"STRING"
            },
            "dict_in_list[0].bytes_list":{
                "type":"LIST"
            },
            "dict_in_list[0].bytes_list[0]":{
                "type":"BYTES"
            },
            "in_list":{
                "type":"LIST"
            },
            "in_list[0]":{
                "type":"BYTES"
            },
            "string_list":{
                "type":"LIST"
            },
            "string_list[0]":{
                "type":"STRING"
            },
            "list_in_list":{
                "type":"LIST"
            },
            "list_in_list[0]":{
                "type":"LIST"
            },
            "list_in_list[0][0]":{
                "type":"BYTES"
            },
            "in_dict":{
                "type":"DICT"
            },
            "in_dict.inside_dict":{
                "type":"BYTES"
            },
            "in_dict.in_list":{
                "type":"LIST"
            },
            "in_dict.in_list[0]":{
                "type":"BYTES"
            },
            "in_dict.dict_in_dict":{
                "type":"DICT"
            },
            "in_dict.dict_in_dict.inside_of_dict":{
                "type":"BYTES"
            },
                "in_dict.list_in_list":{
                "type":"LIST"
            },
            "in_dict.list_in_list[0]":{
                "type":"LIST"
            },
            "in_dict.list_in_list[0][0]":{
                "type":"BYTES"
            }
        }
    }
    convert_b64str_to_bytes(default_req,template)
    expect="{'basic': b'a', 'int': 1, 'string': 'YQ==', 'in_list': [b'a', b'a'], 'string_list': ['YQ==', 'YQ=='], 'dict_in_list': [{'in_dict_list': b'a', 'string': 'YQ==', 'bytes_list': [b'a', b'a']}, {'in_dict_list': b'a', 'string': 'YQ==', 'bytes_list': [b'a', b'a']}], 'list_in_list': [[b'a', b'a'], [b'a', b'a']], 'in_dict': {'inside_dict': b'a', 'in_list': [b'a', b'a'], 'dict_in_dict': {'inside_of_dict': b'a'}, 'list_in_list': [[b'a', b'a'], [b'a', b'a']]}}"
    assert str(default_req) == expect

if __name__ == '__main__':
    app = Flask(__name__)
    app.logger.setLevel(1)
    # app.logger.setLevel(logging.WARNING)
    LOG_FORMAT = "[%(asctime)-15s][%(name)s][%(levelname)s][%(filename)s %(lineno)d] %(message)s"
    formatter = logging.Formatter(LOG_FORMAT)
    sh = logging.StreamHandler()
    # sh.setFormatter(formatter)
    # app.logger.addHandler(sh)
    with app.app_context():
        # BE_input = {"user_id": "INT64", "task_name_list": [{"key":[["STRING"]]},{"key2":[["INT64"]]}], "region": "STRING", "rec":"RECURSIVE","my_dict":{"my_bool":"BOOL","my_uint":"UINT32"}}
        # test_template = default_template(BE_input)
        # default_req = {}
        # gen_default_value(default_req,BE_input)
        # print(f'default_template_gen: {default_req}')

        # template_req = {}
        # gen_default_request_and_template_request(BE_input,default_req,template_req)
        # print(f'default_req = {json.dumps(default_req,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
        # print(f'template_req = {json.dumps(template_req,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
     
        # print(test_template)
        # old_template = {'request': {'task_id': {'is_required': False, 'allow_empty': True, 'skip_checking': False, 'user_input_cases': [], 'range_type': 'RANGE', 'range': ['-9223372036854775808', '9223372036854775807'], 'type': 'INT64', 'default_value': 1}, 'task_name_list[0]': {'is_required': False, 'allow_empty': True, 'skip_checking': False, 'user_input_cases': [], 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'default_value': 'a'}, 'task_name_list': {'is_required': False, 'allow_empty': True, 'skip_checking': False, 'user_input_cases': [], 'range_type': 'NONE', 'range': [], 'type': 'LIST'}, 'region': {'is_required': False, 'allow_empty': True, 'skip_checking': False, 'user_input_cases': [], 'range_type': 'ENUM', 'range': ['SG', 'ID', 'MY', 'PH', 'TH', 'VN', 'TW', 'BR', 'MX', 'CO', 'CL', 'FR', 'ES', 'PL', 'AR', 'IN'], 'type': 'STRING', 'default_value': 'SG'}, 'rec': {'is_required': False, 'allow_empty': True, 'skip_checking': True, 'user_input_cases': [], 'range_type': 'NONE', 'range': [], 'type': 'RECURSIVE', 'default_value': None}, 'my_dict.my_bool': {'is_required': False, 'allow_empty': True, 'skip_checking': False, 'user_input_cases': [], 'range_type': 'RANGE', 'range': [False, True], 'type': 'BOOL', 'default_value': False}, 'my_dict': {'is_required': False, 'allow_empty': True, 'skip_checking': False, 'user_input_cases': [], 'range_type': 'NONE', 'range': [], 'type': 'DICT'}}, 'response': {}, 'default_request': '', 'combination_rules': [], 'error_code_list': []}
        # converted_new_template = structurize_template(test_template)
        # print(f'converted_new_template:\n{json.dumps(converted_new_template,sort_keys=True, indent=4, default=serialize_bytes_base64)}')
        # converted_to_old_template = flatten_template(converted_new_template)
        # print(f'converted_to_old_template:\n{json.dumps(converted_to_old_template,sort_keys=True, indent=4, default=serialize_bytes_base64)}')

        # converted_to_old_template["default_request"]="{\"user_id\": \"1215587845\", \"task_name_list\": [{\"key\": [[1]]}], \"region\": \"SG\", \"rec\": null, \"my_dict\": {\"my_bool\": \"444\"}}"
        # converted_to_old_template["default_request"]="{\"user_id\": 1215587845, \"task_name_list\": [{\"key\": [[\"a\"]]}], \"region\": \"SG\", \"rec\": null, \"my_dict\": {\"my_bool\": \"444\"}}"
        # check_result = check_template(converted_to_old_template)
        # check_result = check_template(input)

        # test_template = default_template({"task_id": "INT64", "region": "STRING","task_list":[{"id":"INT32"}]})
        # test_template = default_template({"task_name_list": ["BYTES"],"my_bytes":"BYTES"})
        # test_template = default_template({"tag_ids": ["UINT32"], "region": "STRING","offset":"UINT32","limit":"UINT32"})
        test_template = default_template({"task_list":["STRING"],"task_name":"STRING","task_id":"UINT32"})
        # myjson = {"request":{"address_id":{"is_required":False,"allow_empty":True,"skip_checking":False,"user_input_cases":[],"range":["-922337203685477","922337203685477"],"default_value":1,"type":"INT64","range_type":"RANGE"},"userid":{"is_required":False,"allow_empty":True,"skip_checking":False,"user_input_cases":[],"range":[-9223372036854776000,9223372036854776000],"default_value":1215587845,"type":"INT64","range_type":"NONE"}},"name":"lky","api_id":"14322"}
        # check_template(myjson)
        # test_template = default_template({"my64": "UINT64"})
        # test_template["request"]["task_id"]["range_type"]="ENUM"
        # test_template["request"]["task_id"]["range"]=[1,100]
        # print(test_template)
        test_template["error_code_list"]= [590001,590002,590005]
        # test_template["default_request"]="{\n     \"task_name_list\": [\"YQ==\"]\n,\"my_bytes\":\"YQ==\"}"
        # test_template["default_request"]="{    \"region\": \"YWE=\"\n,\"task_id\":[\"aa\",\"bb\"]}"
        # test_template["default_request"]="{\n    \"limit\": 1,\n    \"offset\": 1,\n    \"region\": \"SG\",\n    \"tag_ids\": [\n        1,2\n    ]}"

        # test_template["request"]["region"]["is_required"] = True
        # test_template["request"]["task_id"]["allow_empty"] = True
        test_template["request"]["task_name"]["use_unique_value"] = True
        test_template["request"]["task_name"]["range_type"] = "RANGE"
        test_template["request"]["task_name"]["range"] = [0,15]
        test_template["request"]["task_id"]["use_unique_value"] = True
        test_template["request"]["task_list"]["range_type"] = "RANGE"
        test_template["request"]["task_list"]["range"] = ["3",None]
        # test_template["request"]["task_name_list"]["range_type"] = "RANGE"
        # test_template["request"]["task_name_list"]["range"] = [1,4]

        test_template["user_specified_errors"] = {
            "enum_error": [
                118800001
            ],
            "boundary_error": [
                118800002
            ],
            "empty_error": [
                118800020,
                118800002
            ],
            "required_error": [
                118800022
            ]
        }
        # test_template["user_specified_errors"]["parameter_errors"] = [666]
        # test_template["combination_rules"]=["{{task_id}} or {{task_name}}"]
        # test_template["request"]["my64"]["range"]=["1","2"]
        # test_template["request"]["task_id"]["skip_checking"]=True
        # test_template["request"]["task_id"]["skip_checking"]=True
        # test_template["request"]["task_id"]["default_value"]=5

        # test_template["request"]["task_name"]["default_value"]="lkytest"
        # test_template["request"]["task_name"]["range"][1]=2
        # test_template["request"]["task_name"]["range"]=[0,None]
        # test_template["request"]["task_name"]["skip_checking"]=True

        # test_template["request"]["task_id"]["range"][0]=None
        # test_template["request"]["task_id"]["range"][1]=None
   
        
        # test_template["request"]["task_name"]["range_type"]="ENUM"
        # test_template["request"]["task_name"]["range"]=["SG","ID"]
        # print(f'----id={(test_template)}')
        # test_template = {'request': {'to_user_id': {'name': 'to_user_id', 'path': ['to_user_id'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', '4294967295'], 'type': 'UINT32', 'user_input_cases': []}, 'to_shop_id': {'name': 'to_shop_id', 'path': ['to_shop_id'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', '4294967295'], 'type': 'UINT32', 'user_input_cases': []}, 'to_email': {'name': 'to_email', 'path': ['to_email'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'task_name': {'name': 'task_name', 'path': ['task_name'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'task_id': {'name': 'task_id', 'path': ['task_id'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', '4294967295'], 'type': 'UINT32', 'user_input_cases': []}, 'region': {'name': 'region', 'path': ['region'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'ENUM', 'range': ['SG', 'ID', 'MY', 'PH', 'TH', 'VN', 'TW', 'BR', 'MX', 'CO', 'CL', 'FR', 'ES', 'PL', 'AR', 'IN'], 'type': 'STRING', 'user_input_cases': []}, 'language': {'name': 'language', 'path': ['language'], 'is_required': False, 'allow_empty': True, 'skip_checking': True, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'json_data': {'name': 'json_data', 'path': ['json_data'], 'is_required': False, 'allow_empty': True, 'skip_checking': True, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'email_headers.to_emails[0]': {'name': '[0]', 'path': ['email_headers', 'to_emails', '0'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'email_headers.to_emails': {'name': 'to_emails', 'path': ['email_headers', 'to_emails'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'NONE', 'range': [], 'type': 'LIST', 'user_input_cases': []}, 'email_headers.reply_to_emails[0]': {'name': '[0]', 'path': ['email_headers', 'reply_to_emails', '0'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'email_headers.reply_to_emails': {'name': 'reply_to_emails', 'path': ['email_headers', 'reply_to_emails'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'NONE', 'range': [], 'type': 'LIST', 'user_input_cases': []}, 'email_headers.cc_emails[0]': {'name': '[0]', 'path': ['email_headers', 'cc_emails', '0'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'email_headers.cc_emails': {'name': 'cc_emails', 'path': ['email_headers', 'cc_emails'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'NONE', 'range': [], 'type': 'LIST', 'user_input_cases': []}, 'email_headers': {'name': 'email_headers', 'path': ['email_headers'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'NONE', 'range': [], 'type': 'DICT', 'user_input_cases': []}, 'dedupe_id': {'name': 'dedupe_id', 'path': ['dedupe_id'], 'is_required': False, 'allow_empty': True, 'skip_checking': True, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'attachments[0].url': {'name': 'url', 'path': ['attachments', '0', 'url'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'attachments[0].filename': {'name': 'filename', 'path': ['attachments', '0', 'filename'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'RANGE', 'range': ['0', None], 'type': 'STRING', 'user_input_cases': []}, 'attachments[0]': {'name': '[0]', 'path': ['attachments', '0'], 'is_required': False, 'allow_empty': True, 'skip_checking': False, 'range_type': 'NONE', 'range': [], 'type': 'DICT', 'user_input_cases': []}, 'attachments': {'name': 'attachments', 'path': ['attachments'], 'is_required': False, 'allow_empty': True, 'skip_checking': True, 'range_type': 'NONE', 'range': [], 'type': 'LIST', 'user_input_cases': []}}, 'response': {}, 'error_code_list': [46100000, 46100001, 46100002, 46100003, 46100004, 46100005, 46100006, 46100007, 46100008, 46100009, 46100010, 46101000, 46101001, 46101002, 46101003], 'default_request': '{\n\t"task_id": 207,\n\t"region": "SG",\n\t"language": "EN",\n  "json_data": "{\\"order\\": {\\"items\\": [{\\"name\\": \\"\\", \\"photo\\": \\"\\", \\"price\\": 1000000000000, \\"itemid\\": \\"12345\\", \\"models\\": [{\\"name\\": \\"televisor\\", \\"price\\": 1000000000, \\"quantity\\": \\"1\\"}], \\"shopid\\": \\"12345\\", \\"quantity\\": \\"1\\", \\"refunded\\": true, \\"is_have_discount\\": true, \\"price_before_disconut\\": 10000000}], \\"orderid\\": \\"1234512321\\", \\"ordersn\\": \\"1234214\\", \\"currency\\": \\"\\", \\"create_time\\": 1626678399, \\"actual_price\\": 11111111111110, \\"shipping_fee\\": 11111111110, \\"order_subtotal\\": 1111111111111110, \\"seller_discount\\": 11111111111110}}",\n  "to_email": "evan.zhang@shopee.com",\n  "attachments": []\n}', 'combination_rules': ['{{to_email}} or {{to_shop_id}} or {{to_user_id}}', '{{task_name}} or {{task_id}}']} 

        check_result = check_template(test_template)
        print(f'check_result: {check_result}')

        # structurize_template(test_template)

        # default_request = get_default_request(test_template['request'])
        
        cases = generate_cases("","",test_template)
        # exit()

