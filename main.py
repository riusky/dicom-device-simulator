import questionary
import os
import json
from questionary import Choice
from questionary import Separator
from questionary import prompt
from questionary import Style
from pprint import pprint
from pydicom.uid import generate_uid
import re

from json_utils import json_file_exists, read_json_file, write_json_file, update_json_file, ensure_directory_exists
from dicom_utils import get_work_list, extract_fields, send_mpps_in_progress, send_n_set, collect_dcm_files, send_c_store_requests, send_mpps_discontinued, build_mod_list
from ask_questionary import ask_settings, ask_main, ask_mpps

custom_style_dope = Style(
    [
        ("question", "fg:#f44336 bold"),
        ("selected", "fg:#2196f3 bold"),
        ("answer", "fg:#2196f3 bold"),
        ("pointer", "fg:#FF9D00 bold"),
        # ("highlighted", "fg:#673ab7 bold"),
        ("separator", "fg:#cc5454"),
        ("disabled", "fg:#858585 italic"),
    ]
)

setting_json_path = "data_base/setting/setting.json"
default_setting_json_path = "system_data/default_setting.json"
mpps_json_path = "data_base/mpps/"

def ask_language(**kwargs):
    questions = [
        {
            "type": "select",
            "name": "theme",
            "message": "😃 What language do you want to use?",
            "choices": [
                "English",
                "Chinese",
                Separator(),
                {"name": "Custom", "disabled": "Unavailable at this time"},
            ],
        }
    ]
    return prompt(questions, style=custom_style_dope, **kwargs)

def validate(text):
    match = re.match(
        r"^(((25[0-5]|2[0-4]d|((1\d{2})|([1-9]?\d)))\.){3}(25[0-5]|2[0-4]\d|((1\d{2})|([1-9]?\d))))\:([0-9]|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{4}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$",
        text
    )
    if not match:
        return False
    return True

def ask_address_port(prompt_message,default_address):
    run_flag = True
    while run_flag:
        address_port = questionary.text(prompt_message).ask()
        if not address_port:
            address_port = default_address
        if validate(address_port):
            run_flag = False
            return address_port
        else:
            questionary.print("Invalid address or port. Please try again.", style="bold fg:red")

def init_project(json_file_exists, read_json_file, write_json_file, ask_language):
    setting_json = None
    global setting_json_path
    global default_setting_json_path
    setting_json_path_exists = json_file_exists(setting_json_path)
    
    if setting_json_path_exists:
        setting_json = read_json_file(setting_json_path)
        formatted_json = json.dumps(setting_json, indent=4)
        print(formatted_json)
        questionary.print("😃 Here is the current configuration!", style="bold italic fg:#00bc12")
    else:
        questionary.print("🤣 The program is not initialized, please initialize the configuration first", style="bold italic fg:#ff2121")
        default_setting_json = read_json_file(default_setting_json_path)
        formatted_json = json.dumps(default_setting_json, indent=4)
        questionary.print("😃 Here is the default configuration!", style="bold italic fg:#00bc12")
        print(formatted_json)
        
        use_default = questionary.confirm("Do you want to use the default configuration?").ask()
        
        if not use_default:
            # language = ask_language()
            language = 'English'
            wml_address = ask_address_port("Great! 👍 Now, please provide your Worklist address and port. Press Enter to use the default (127.0.0.1:106):", "127.0.0.1:106")
            mpps_address = ask_address_port("Great! 👍 Now, please provide your MPPS address and port. Press Enter to use the default (127.0.0.1:107):", "127.0.0.1:107")
            pacs_address = ask_address_port("Great! 👍 Now, please provide your PACS address and port. Press Enter to use the default (127.0.0.1:11112):", "127.0.0.1:11112")
            
            calling_ae_title = questionary.text("Great! 👍 Now, please provide your modality AE title. Press Enter to use the default (ct99):").ask()
            if not calling_ae_title:
                calling_ae_title = "ct99"
                
            wml_ae_title = questionary.text("Great! 👍 Now, please provide the WML AE title. Press Enter to use the default (ENS-MWL):").ask()
            if not wml_ae_title:
                wml_ae_title = "ENS-MWL"
                
            mpps_ae_title = questionary.text("Great! 👍 Now, please provide the MPPS AE title. Press Enter to use the default (ENS-MPPS):").ask()
            if not mpps_ae_title:
                mpps_ae_title = "ENS-MPPS"
                
            pacs_ae_title = questionary.text("Great! 👍 Now, please provide the PACS AE title. Press Enter to use the default (ENS-PACS):").ask()
            if not pacs_ae_title:
                pacs_ae_title = "ENS-PACS"
                
            log = questionary.confirm("Do you want to enable runtime logs?").ask()
            
            ct_default_path = questionary.path("Path to the CT images file or directory. Press Enter to use the default (./system_data/dcm/ct):").ask()
            if not ct_default_path:
                ct_default_path = "./system_data\\/dcm\\/ct"
                
            mr_default_path = questionary.path("Path to the MR images file or directory. Press Enter to use the default (./system_data/dcm/mr):").ask()
            if not mr_default_path:
                mr_default_path = "./system_data\\/dcm\\/mr"
                
            setting_json = {
                "language": language,
                "wml_address": wml_address,
                "mpps_address": mpps_address,
                "pacs_address": pacs_address,
                "debug": log,
                "calling_ae_title": calling_ae_title,
                "wml_ae_title": wml_ae_title,
                "mpps_ae_title": mpps_ae_title,
                "pacs_ae_title": pacs_ae_title,
                "ct_default_path": ct_default_path,
                "mr_default_path": mr_default_path,
            }
        else:
            setting_json = default_setting_json
        
        write_json_file(setting_json_path, setting_json)
        init_project(json_file_exists, read_json_file, write_json_file, ask_language)





def ask_mpps_option(filename, **kwargs):
    mpps_json = None
    choices = [
        {"name": "SEND IN PROGRESS", "disabled": False},
        {"name": "SEND DISCONTINUED", "disabled": False},
        {"name": "SEND COMPLETED DEFAULT IMAGES", "disabled": False},
        {"name": "SEND COMPLETED CUSTOM IMAGES", "disabled": False},
        {"name": "SEND TO PACS DEFAULT ADDRESS", "disabled": False},
        {"name": "SEND TO PACS CUSTOM ADDRESS", "disabled": False},
        {"name": "exit", "disabled": False},
    ]

    setting_json_path_is_exist = json_file_exists(mpps_json_path + filename)
    if not setting_json_path_is_exist:
        for choice in choices:
            if choice["name"] != "SEND IN PROGRESS" and choice["name"] != "exit":
                choice["disabled"] = "Not Yet IN PROGRESS!"
    else:
        mpps_json = read_json_file(mpps_json_path + filename)
        current_state = mpps_json.get("currentState")
        if current_state == "IN PROGRESS":
            for choice in choices:
                if choice["name"] not in ["SEND DISCONTINUED", "SEND COMPLETED DEFAULT IMAGES","SEND COMPLETED CUSTOM IMAGES", "exit"]:
                    choice["disabled"] = "Invalid state"
        elif current_state == "DISCONTINUED":
            for choice in choices:
                if choice["name"] not in ["exit"]:
                    choice["disabled"] = "Invalid state"
        elif current_state == "COMPLETED":
            for choice in choices:
                if choice["name"] not in ["SEND TO PACS DEFAULT ADDRESS", "SEND TO PACS CUSTOM ADDRESS", "exit"]:
                    choice["disabled"] = "Invalid state"
        else:
            for choice in choices:
                if choice["name"] != "SEND IN PROGRESS" and choice["name"] != "exit":
                    choice["disabled"] = "Not Yet IN PROGRESS!"

    questions = [
        {
            "type": "select",
            "name": "theme",
            "message": "😎 Now! Which choice do you want to make?",
            "choices": choices,
        },
    ]
    
    return prompt(questions, style=custom_style_dope, **kwargs)


def paper_menu(filename):
    setting_json = read_json_file(setting_json_path)
    mpps_json_data = None
    setting_json_path_is_exist = json_file_exists(mpps_json_path + filename)
    if not setting_json_path_is_exist:
        return
    else:
        mpps_json_data = read_json_file(mpps_json_path + filename)
    mpps_json_data['currentState'] ="COMPLETED"
    path = questionary.path("🚀🚀🚀 Path to the images dcm file? use '/' to select directory or file:").ask()
    sop_instance_uids = collect_dcm_files(path)
    if sop_instance_uids:
        mpps_json_data['sop_instance_uids'] = sop_instance_uids
        mpps_json_data['dcm_file'] = path
        update_json_file(mpps_json_path + filename, mpps_json_data)
        ds = build_mod_list(mpps_json_data)
        send_n_set(mpps_json_data, setting_json, ds)
    return
def paper_menu_default(filename):
    setting_json = read_json_file(setting_json_path)
    mpps_json_data = None
    setting_json_path_is_exist = json_file_exists(mpps_json_path + filename)
    if not setting_json_path_is_exist:
        print(f"Invalid option: json file is not exist {mpps_json_path} {filename}")
        return
    else:
        mpps_json_data = read_json_file(mpps_json_path + filename)
    mpps_json_data['currentState'] ="COMPLETED"
    Modality = mpps_json_data['data']['Modality']
    if Modality == 'CT':
        path = setting_json['ct_default_path']
    elif Modality == 'MR':
        path = setting_json['mr_default_path']
    else:
        print(f"Invalid option: Modality is not CT or MR: {Modality}")
        return
    sop_instance_uids = collect_dcm_files(path)
    if sop_instance_uids:
        mpps_json_data['sop_instance_uids'] = sop_instance_uids
        mpps_json_data['dcm_file'] = path
        update_json_file(mpps_json_path + filename, mpps_json_data)
        ds = build_mod_list(mpps_json_data)
        send_n_set(mpps_json_data, setting_json, ds)
    return


def ask_pacs(pacs_info, **kwargs):
    if not pacs_info:
        pacs_choices = [
            Separator(f'=============== NO PACS PLEASE ADD A PACS===============')
        ]
    else:
        pacs_choices = [
            Choice(
                title=f"Name: {pacs['name']}, IP: {pacs['pacs_address'].split(":")[0]}, Port: {int(pacs["pacs_address"].split(":")[1])}, AE Title: {pacs['pacs_ae_title']}",
                value=pacs
            )
            for pacs in pacs_info
        ]
    
    questions = [
        {
            "type": "select",
            "name": "pacs_choice",
            "message": "📡 Select a PACS server:",
            "choices": pacs_choices + [Separator(f'=============== ADD PACS ==============='), Choice("ADD PACS", value="ADD PACS"),Separator(f'=============== {exit} ==============='), Choice("exit", value="exit")]
        }
    ]

    return prompt(questions, style=custom_style_dope, **kwargs)

def paper_to_pacs_menu_custom(filename):
    global setting_json_path
    setting_json = read_json_file(setting_json_path)
    mpps_json_data = None
    setting_json_path_is_exist = json_file_exists(mpps_json_path + filename)
    if not setting_json_path_is_exist:
        print(f"Invalid option: json file is not exist {mpps_json_path} {filename}")
        return
    else:
        mpps_json_data = read_json_file(mpps_json_path + filename)
    if mpps_json_data:
        selected_pacs = ask_pacs(setting_json.get('pacs_info',''))
        if not selected_pacs:
            return
        elif selected_pacs['pacs_choice'] == "exit":
            return
        elif selected_pacs['pacs_choice'] == "ADD PACS":
            ask_settings()
        else:
            selected_pacs_data = selected_pacs['pacs_choice']
            custom_setting_json = {
                "calling_ae_title":setting_json["calling_ae_title"],
                "pacs_ae_title":selected_pacs_data["pacs_ae_title"],
                "pacs_address":selected_pacs_data["pacs_address"],
            }
            send_c_store_requests(mpps_json_data, custom_setting_json)
    return

def paper_to_pacs_menu_default(filename):
    setting_json = read_json_file(setting_json_path)
    mpps_json_data = None
    setting_json_path_is_exist = json_file_exists(mpps_json_path + filename)
    if not setting_json_path_is_exist:
        print(f"Invalid option: json file is not exist {mpps_json_path} {filename}")
        return
    else:
        mpps_json_data = read_json_file(mpps_json_path + filename)
    if mpps_json_data:
        send_c_store_requests(mpps_json_data, setting_json)
    return


def exec_mpps():
    setting_json = read_json_file(setting_json_path)
    global mpps_json_path
    exit_flag = False
    while not exit_flag:
        mpps_info = ask_mpps()
        if not mpps_info or mpps_info['theme'] == "exit":
            exit_flag = True
            continue
        else:
            ip_address, port = setting_json['mpps_address'].split(':')
            port = int(port)
            mpps_exit_flag = False
            while not mpps_exit_flag:
                mpps_option = ask_mpps_option(mpps_info['theme']['StudyInstanceUID']+'.json')
                if not mpps_option or mpps_option['theme'] == 'exit':
                    mpps_exit_flag = True
                    continue
                mpps_option_theme = mpps_option['theme']
                mpps_json_data = None
                setting_json_path_is_exist = json_file_exists(mpps_json_path + mpps_info['theme']['StudyInstanceUID']+'.json')
                if not setting_json_path_is_exist:
                    mpps_json_data = {
                        "data": mpps_info['theme'],
                    }
                else:
                    mpps_json_data = read_json_file(mpps_json_path + mpps_info['theme']['StudyInstanceUID']+'.json')
                if mpps_option_theme == "SEND IN PROGRESS":
                    mpps_json_data['currentState'] = "IN PROGRESS"
                    mpps_instance_uid = send_mpps_in_progress(setting_json['calling_ae_title'],setting_json['mpps_ae_title'],ip_address,port,mpps_json_data,setting_json['debug'])
                    if mpps_instance_uid:
                        mpps_json_data['mpps_instance_uid'] = mpps_instance_uid
                        write_json_file(mpps_json_path + mpps_info['theme']['StudyInstanceUID']+'.json',mpps_json_data)
                elif mpps_option_theme == "SEND DISCONTINUED":
                    mpps_json_data['currentState'] = "DISCONTINUED"
                    mpps_instance_uid = send_mpps_discontinued(setting_json['calling_ae_title'],setting_json['mpps_ae_title'],ip_address,port,mpps_json_data,setting_json['debug'])
                    if mpps_instance_uid:
                        write_json_file(mpps_json_path + mpps_info['theme']['StudyInstanceUID']+'.json',mpps_json_data)
                elif mpps_option_theme == "SEND COMPLETED DEFAULT IMAGES":
                    paper_menu_default(mpps_info['theme']['StudyInstanceUID']+'.json')
                elif mpps_option_theme == "SEND COMPLETED CUSTOM IMAGES":
                    paper_menu(mpps_info['theme']['StudyInstanceUID']+'.json')
                elif mpps_option_theme == "SEND TO PACS DEFAULT ADDRESS":
                    paper_to_pacs_menu_default(mpps_info['theme']['StudyInstanceUID']+'.json')
                elif mpps_option_theme == "SEND TO PACS CUSTOM ADDRESS":
                    paper_to_pacs_menu_custom(mpps_info['theme']['StudyInstanceUID']+'.json')
                    continue
                else:
                    print("Invalid option")


if __name__ == "__main__":
    questionary.print("😃 Hello, please follow the instructions below to select the operation!", style="bold italic fg:#00bc12")
    # setting_json_path = "data_base/setting/setting.json"
    init_project(json_file_exists, read_json_file, write_json_file, ask_language)
    exit_flag = False
    while not exit_flag:
        main_option = ask_main()
        if not main_option or main_option['theme'] == "exit":
            exit_flag = True
            continue
        main_option_theme = main_option['theme']
        if main_option_theme == "View work list":
            mpps_info = ask_mpps()
            print(mpps_info)
        elif main_option_theme == "Push an MPPS message":
            exec_mpps()        
        elif main_option_theme == "SETTING":
            ask_settings()
        else:
            questionary.print("option: ! " + main_option_theme, style="bold italic fg:#ff0000")
