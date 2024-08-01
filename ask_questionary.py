import json
import questionary
from questionary import Choice
from questionary import Separator
from questionary import prompt
from questionary import Style
import uuid
from json_utils import json_file_exists, read_json_file, write_json_file, update_json_file, ensure_directory_exists
from dicom_utils import get_work_list, extract_fields, send_mpps_in_progress, send_n_set, collect_dcm_files, send_c_store_requests, send_mpps_discontinued, build_mod_list
import os

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
def load_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def save_data(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def edit_general_setting(data, setting_key):
    current_value = data.get(setting_key, "")
    if isinstance(current_value, bool):
        new_value = questionary.confirm(f"Enter new value for {setting_key}:", default=current_value).ask()
    else:
        new_value = questionary.text(f"Enter new value for {setting_key}:", default=current_value).ask()
    if new_value is not None:
        data[setting_key] = new_value

def add_pacs_info(data):
    name = None
    pacs_address = questionary.text("Enter PACS address:").ask()
    pacs_ae_title = questionary.text("Enter PACS AE Title:").ask()
    name = questionary.text("Enter PACS name:").ask()
    while True:
        if any(pacs["name"] == name for pacs in data["pacs_info"]):
            print("Name already exists. Please enter a unique name.")
            name = questionary.text("Enter PACS name:").ask()
        break

    new_pacs = {
        "name": name,
        "pacs_address": pacs_address,
        "pacs_ae_title": pacs_ae_title,
        "uuid": str(uuid.uuid4())
    }
    data["pacs_info"].append(new_pacs)

def edit_pacs_info(data):
    pacs_choices = [pacs["name"] for pacs in data["pacs_info"]] + ["Exit"]
    choice = questionary.select("Select PACS to edit:", choices=pacs_choices).ask()

    if choice == "Exit":
        return

    pacs = next(p for p in data["pacs_info"] if p["name"] == choice)
    new_pacs_address = questionary.text("Enter new PACS address:", default=pacs["pacs_address"]).ask()
    new_pacs_ae_title = questionary.text("Enter new PACS AE Title:", default=pacs["pacs_ae_title"]).ask()
    new_name = None
    while not new_name:
        new_name = questionary.text("Enter new PACS name:", default=pacs["name"]).ask()
        if new_name != pacs["name"] and any(p["name"] == new_name for p in data["pacs_info"]):
            print("Name already exists. Please enter a unique name.")
            new_name = None

    pacs["pacs_address"] = new_pacs_address
    pacs["pacs_ae_title"] = new_pacs_ae_title
    pacs["name"] = new_name

def delete_pacs_info(data):
    pacs_choices = [pacs["name"] for pacs in data["pacs_info"]] + ["Exit"]
    choice = questionary.select("Select PACS to delete:", choices=pacs_choices).ask()

    if choice == "Exit":
        return

    data["pacs_info"] = [p for p in data["pacs_info"] if p["name"] != choice]
    
    
def ask_settings():
    global setting_json_path
    data = read_json_file(setting_json_path)
    while True:
        choice = questionary.select(
            "Choose an action:",
            choices=[
                "Edit General Language",
                "Edit General Wml_Address",
                "Edit General Mpps_Address",
                "Edit General Pacs_Address",
                "Edit General Debug",
                "Edit General Wml_AE_Title",
                "Edit General Mpps_AE_Title",
                "Edit General Calling_AE_Title",
                "Edit General Pacs_AE_Title",
                "Edit General CT_Default_Path",
                "Edit General MR_Default_Path",
                "Add PACS Info",
                "Edit PACS Info",
                "Delete PACS Info",
                "Exit"
            ]
        ).ask()
        if choice == "Exit":
            break
        elif choice.startswith("Edit General "):
            setting_key = choice.replace("Edit General ", "").lower()
            edit_general_setting(data, setting_key)
        elif choice == "Add PACS Info":
            add_pacs_info(data)
        elif choice == "Edit PACS Info":
            edit_pacs_info(data)
        elif choice == "Delete PACS Info":
            delete_pacs_info(data)
        save_data(data, setting_json_path)
        
def ask_main(**kwargs):
    questions = [
        {
            "type": "select",
            "name": "theme",
            "message": "😎 Now! What do you want to do?",
            "choices": [
                "View work list",
                "Push an MPPS message",
                # "Delete all data",
                "SETTING",
                "exit",
            ],
        },
    ]

    return prompt(questions, style=custom_style_dope, **kwargs)

# MPPS
def ask_mpps(**kwargs):
    global mpps_json_path
    global setting_json_path
    setting_json = read_json_file(setting_json_path)
    ip_address, port = setting_json['wml_address'].split(':')
    port = int(port)
    wml = get_work_list(setting_json['calling_ae_title'], setting_json['wml_ae_title'], ip_address, port, setting_json['debug'])
    
    choices = []
    if wml:
        extracted_data = [extract_fields(item) for item in wml]
        choices = [
            Choice(
                title=f"AccessionNr: {item['AccessionNumber']}, ReqProcId: {item['RequestedProcedureDescription']}, PatientName: {item['PatientName']}, PatientID: {item['PatientID']}, PatientBirthDate: {item['PatientBirthDate']}, Sex: {item['PatientSex']}, Modality: {item['Modality']}, SPStartDate: {item['ScheduledProcedureStepStartDate']}, SPPhysicianName: {item['ScheduledPerformingPhysicianName']}",
                value=item
            )
            for item in extracted_data
        ]
    
    grouped_data = {"IN PROGRESS": [], "DISCONTINUED": [], "COMPLETED": []}

    # Loop through JSON files in the specified directory
    ensure_directory_exists(mpps_json_path)
    for json_file in os.listdir(mpps_json_path):
        if json_file.endswith('.json'):
            file_path = os.path.join(mpps_json_path, json_file)
            json_data = read_json_file(file_path)
            if not json_data:
                continue
            data = json_data['data']
            current_state = json_data.get('currentState', 'UNKNOWN')
            
            if current_state in grouped_data:
                grouped_data[current_state].append(data)
            else:
                continue
    
    state_order = ["IN PROGRESS", "DISCONTINUED", "COMPLETED"]
    for state in state_order:
        if grouped_data[state]:
            choices.append(Separator(f'=============== {state} ==============='))
            # Sort each group by AccessionNumber in ascending order
            sorted_group = sorted(grouped_data[state], key=lambda x: x['AccessionNumber'])
            for data in sorted_group:
                choices.append(
                    Choice(
                        title=f"AccessionNr: {data['AccessionNumber']}, ReqProcId: {data['RequestedProcedureDescription']}, PatientName: {data['PatientName']}, PatientID: {data['PatientID']}, PatientBirthDate: {data['PatientBirthDate']}, Sex: {data['PatientSex']}, Modality: {data['Modality']}, SPStartDate: {data['ScheduledProcedureStepStartDate']}, SPPhysicianName: {data['ScheduledPerformingPhysicianName']}",
                        value=data
                    )
                )
    choices.append(Separator(f'=============== {exit} ==============='))
    choices.append(Choice("exit", value="exit"))
    
    questions = [
        {
            "type": "select",
            "name": "theme",
            "message": "😃 Please select a message and proceed?",
            "choices": choices
        },
    ]
    
    return prompt(questions, style=custom_style_dope, **kwargs)