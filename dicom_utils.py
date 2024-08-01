from pydicom.dataset import Dataset
from pydicom.uid import generate_uid
from pynetdicom import AE, debug_logger, build_context
from pynetdicom.sop_class import (
    ModalityWorklistInformationFind,
    ModalityPerformedProcedureStep,
    CTImageStorage
)
from pynetdicom.status import code_to_category
import json
from datetime import datetime
from pydicom import dcmread
import os
from collections import defaultdict
import copy
from pynetdicom.sop_class import uid_to_sop_class


# Utility function to establish association
def establish_association(calling_ae_title, ae_title, ae_address, ae_port, context, debug=False):
    if debug:
        debug_logger()
    
    ae = AE(calling_ae_title)
    ae.add_requested_context(context)
    assoc = ae.associate(ae_address, ae_port, ae_title=ae_title)
    
    if not assoc.is_established:
        print('Association rejected, aborted or never connected')
        return None
    
    return assoc

# Utility function to send C-FIND request
def send_c_find(assoc, ds):
    responses = assoc.send_c_find(ds, ModalityWorklistInformationFind, msg_id=99)
    result = []

    for status, identifier in responses:
        if status:
            print('C-FIND query status: 0x{0:04x}'.format(status.Status))
        if identifier:
            result.append(identifier.to_json())
        else:
            print('Connection timed out, was aborted or received invalid response')

    return result

# Function to get work list
def get_work_list(calling_ae_title, ae_title, ae_address, ae_port, debug=False):
    ds = dcmread('./system_data/message/C-FIND-RQ.dcm')
    assoc = establish_association(calling_ae_title, ae_title, ae_address, ae_port, ModalityWorklistInformationFind, debug)
    if assoc is None:
        return []
    result = send_c_find(assoc, ds)
    assoc.release()
    return result

# Function to extract fields from DICOM data
def extract_fields(data):
    dicom_data = json.loads(data)
    result = {
        "AccessionNumber": dicom_data.get("00080050", {}).get("Value", [""])[0],
        "RequestedProcedureDescription": dicom_data.get("00401001", {}).get("Value", [""])[0],
        "PatientName": dicom_data.get("00100010", {}).get("Value", [{}])[0].get("Alphabetic", ""),
        "PatientID": dicom_data.get("00100020", {}).get("Value", [""])[0],
        "PatientBirthDate": dicom_data.get("00100030", {}).get("Value", [""])[0],
        "PatientSex": dicom_data.get("00100040", {}).get("Value", [""])[0],
        'Modality': dicom_data.get("00400100", {}).get("Value", [""])[0].get("00080060", {}).get("Value", [""])[0],
        'ScheduledStationAETitle': dicom_data.get("00400100", {}).get("Value", [""])[0].get("00400001", {}).get("Value", [""])[0],
        'ScheduledProcedureStepStartDate': dicom_data.get("00400100", {}).get("Value", [""])[0].get("00400002", {}).get("Value", [""])[0],
        'ScheduledPerformingPhysicianName': dicom_data.get("00400100", {}).get("Value", [""])[0].get("00400006", {}).get("Value", [""])[0].get("Alphabetic", ""),
        'StudyInstanceUID': dicom_data.get("0020000D", {}).get("Value", [""])[0],
    }
    return result

# Function to build attribute list for N-CREATE
def build_attr_list_in_progress(data, PerformedProcedureStepStatus):
    ct_study_uid = data.get('StudyInstanceUID', '')
    ds = dcmread('./system_data/message/mpps-inprogress.dcm')
    # ds.ScheduledStepAttributesSequence = [Dataset()]
    step_seq = ds.ScheduledStepAttributesSequence
    ct_study_uid = data.get('StudyInstanceUID', '')
    step_seq[0].StudyInstanceUID = ct_study_uid
    step_seq[0].ReferencedStudySequence[0].SpecificCharacterSet = 'ISO_IR 100'
    # del step_seq[0].ReferencedStudySequence[0].ReferencedSOPInstanceUID
    step_seq[0].AccessionNumber = data.get('AccessionNumber', '')
    step_seq[0].RequestedProcedureID = data.get('RequestedProcedureDescription', '')
    step_seq[0].RequestedProcedureDescription = data.get('RequestedProcedureDescription', '')
    step_seq[0].ScheduledProcedureStepID = data.get('RequestedProcedureDescription', '')
    step_seq[0].ScheduledProcedureStepDescription = data.get('RequestedProcedureDescription', '')
    step_seq[0].ScheduledProcedureProtocolCodeSequence = []
    ds.PatientName = data.get('PatientName', '')
    ds.PatientID = data.get('PatientID', '')
    ds.PatientBirthDate = data.get('PatientBirthDate', '')
    ds.PatientSex = data.get('PatientSex', '')
    ds.ReferencedPatientSequence = []
    ds.PerformedProcedureStepID = 'PPS ID ' + data.get('AccessionNumber', '')
    ds.PerformedStationAETitle = data.get('ScheduledStationAETitle', '')
    ds.PerformedStationName = data.get('ScheduledStationAETitle', '')
    ds.PerformedLocation = data.get('ScheduledStationAETitle', '')
    ds.PerformedProcedureStepStartDate = data.get('ScheduledProcedureStepStartDate', '')
    now = datetime.now()
    time_int_str = now.strftime("%H%M%S")
    ds.PerformedProcedureStepStartTime = time_int_str
    ds.PerformedProcedureStepStatus = PerformedProcedureStepStatus
    ds.PerformedProcedureStepDescription = 'description'
    ds.PerformedProcedureTypeDescription = 'type'
    ds.PerformedProcedureCodeSequence = []
    ds.PerformedProcedureStepEndDate = None
    ds.PerformedProcedureStepEndTime = None
    ds.Modality = data.get('Modality', '')
    ds.StudyID = data.get('AccessionNumber', '')
    ds.PerformedProtocolCodeSequence = []
    ds.PerformedSeriesSequence = []
    ds.PerformedProcedureStepDiscontinuationReasonCodeSequence = []
    return ds
def build_attr_list_discontinued(data, PerformedProcedureStepStatus):
    ds = dcmread('./system_data/message/mpps-discontinued.dcm')
    # ds.ScheduledStepAttributesSequence = [Dataset()]
    step_seq = ds.PerformedSeriesSequence
    step_seq[0].SeriesInstanceUID = generate_uid()
    step_seq[0].ReferencedImageSequence = []
    now = datetime.now()
    time_int_str = now.strftime("%H%M%S")
    date_int_str = now.strftime('%Y%m%d')
    ds.PerformedProcedureStepStatus = PerformedProcedureStepStatus
    ds.PerformedProcedureStepEndDate = date_int_str
    ds.PerformedProcedureStepEndTime = time_int_str
    return ds

# Function to send N-CREATE request
def send_mpps_in_progress(calling_ae_title, ae_title, ae_address, ae_port, data, debug=False):
    assoc = establish_association(calling_ae_title, ae_title, ae_address, ae_port, ModalityPerformedProcedureStep, debug)
    if assoc is None:
        return None
    result = None
    if data.get('mpps_instance_uid'):
        result = data.get('mpps_instance_uid')
    else:
        result = generate_uid()
    ds = build_attr_list_in_progress(data['data'], data['currentState'])
    status, attr_list = assoc.send_n_create(ds, ModalityPerformedProcedureStep, result)
    
    if status:
        print('N-CREATE request status: 0x{0:04x}'.format(status.Status))
    else:
        print('Connection timed out, was aborted or received invalid response')
        result = None
    
    assoc.release()
    return result

def send_mpps_discontinued(calling_ae_title, ae_title, ae_address, ae_port, data, debug=False):
    assoc = establish_association(calling_ae_title, ae_title, ae_address, ae_port, ModalityPerformedProcedureStep, debug)
    if assoc is None:
        return None
    result = None
    if data.get('mpps_instance_uid'):
        result = data.get('mpps_instance_uid')
    else:
        result = generate_uid()
    
    ds = build_attr_list_discontinued(data['data'], data['currentState'])
    status, attr_list = assoc.send_n_set(ds, ModalityPerformedProcedureStep, result)
    
    if status:
        print('N-CREATE request status: 0x{0:04x}'.format(status.Status))
    else:
        print('Connection timed out, was aborted or received invalid response')
        result = None
    
    assoc.release()
    return result

# Function to build attribute list for N-SET
def build_mod_list(json_data):
    sop_instance_info = json_data["sop_instance_uids"]
    patient_data = json_data["data"]
    ds = dcmread('./system_data/message/mpps-completed.dcm')
    now = datetime.now()
    ds.PerformedProcedureStepEndDate = now.strftime('%Y%m%d')
    ds.PerformedProcedureStepEndTime = now.strftime('%H%M')
    performedSeriesSequenceTemplate = ds.PerformedSeriesSequence[0]
    referencedImageSequenceTemplate = ds.PerformedSeriesSequence[0].ReferencedImageSequence[0]
    ds.PerformedSeriesSequence = []
    for i, series_info in enumerate(sop_instance_info):
        performedSeriesSequence = copy.deepcopy(performedSeriesSequenceTemplate)
        performedSeriesSequence.SeriesInstanceUID = series_info['series_instance_uid']
        performedSeriesSequence.PerformingPhysicianName = patient_data['ScheduledPerformingPhysicianName']
        performedSeriesSequence.OperatorsName = 'iRT DICOM Device Simulator'
        performedSeriesSequence.SeriesDescription = 'iRT DICOM Device Simulator'
        performedSeriesSequence.ReferencedImageSequence = []
        for instance in series_info['sop_instance_infos']:
            referencedImageSequence = copy.deepcopy(referencedImageSequenceTemplate)
            referencedImageSequence.ReferencedSOPClassUID = series_info['SOPClassUID']
            referencedImageSequence.ReferencedSOPInstanceUID = instance['sop_instance_uid']
            performedSeriesSequence.ReferencedImageSequence.append(referencedImageSequence)
        ds.PerformedSeriesSequence.append(performedSeriesSequence)

    return ds

# Function to send N-SET request
def send_n_set(json_data, settings, ds):
    if settings["debug"]:
        debug_logger()

    assoc = establish_association(
        settings["calling_ae_title"],
        settings["mpps_ae_title"],
        settings["mpps_address"].split(":")[0],
        int(settings["mpps_address"].split(":")[1]),
        ModalityPerformedProcedureStep,
        settings["debug"]
    )

    if assoc is None:
        return None

    # Send the N-SET request for the series
    status, attr_list = assoc.send_n_set(
        ds,
        ModalityPerformedProcedureStep,
        json_data["mpps_instance_uid"]
    )

    if status:
        print('N-SET MPPS request status: 0x{0:04x}'.format(status.Status))
        # final_ds = Dataset()
        # final_ds.PerformedProcedureStepStatus = "COMPLETED"
        # now = datetime.now()
        # final_ds.PerformedProcedureStepEndDate = now.strftime('%Y%m%d')
        # final_ds.PerformedProcedureStepEndTime = now.strftime('%H%M')
        # category = code_to_category(status.Status)
        # if category in ['Warning', 'Success']:
        #     # Send completion status
        #     status, attr_list = assoc.send_n_set(
        #         final_ds,
        #         ModalityPerformedProcedureStep,
        #         json_data["mpps_instance_uid"]
        #     )
        #     if status:
        #         print('Final N-SET request status: 0x{0:04x}'.format(status.Status))
    else:
        print('Connection timed out, was aborted or received invalid response')

    assoc.release()
    return status


def collect_dcm_files(path):
    sop_instance_uids = []
    
    if not os.path.exists(path):
        print("not exist path")
        return sop_instance_uids

    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".dcm"):
                ds = dcmread(os.path.join(root, file))
                is_exist = 'SOPClassUID' in ds
                if is_exist:
                    SOPClassUID = ds.SOPClassUID
                    sop_instance_uid = {
                        "sop_instance_uid": generate_uid(),
                        "path": os.path.join(root, file),
                        "SOPClassUID": SOPClassUID
                    }
                    sop_instance_uids.append(sop_instance_uid)
    if sop_instance_uids:
        categorized_data = defaultdict(list)

        for item in sop_instance_uids:
            categorized_data[item['SOPClassUID']].append({
                'sop_instance_uid': item['sop_instance_uid'],
                'path': item['path']
            })
        result = [
            {
                'SOPClassUID': sop_class_uid,
                'series_instance_uid': generate_uid(),
                'sop_instance_infos': infos
            }
            for sop_class_uid, infos in categorized_data.items()
        ]
        return result
    return sop_instance_uids

# Function to send C-STORE requests
def send_c_store_requests(json_data, settings):
    calling_ae_title = settings["calling_ae_title"]
    pacs_ae_title = settings["pacs_ae_title"]
    ip = settings["pacs_address"].split(":")[0]
    port = int(settings["pacs_address"].split(":")[1])
    # Initialise the Application Entity
    ae = AE(ae_title=calling_ae_title)
    patient_data = json_data["data"]
    # Loop through the JSON data
    for item in json_data["sop_instance_uids"]:
        sop_class_uid = item["SOPClassUID"]
        sop_class = uid_to_sop_class(sop_class_uid)
        if sop_class is None:
            print(f"Unsupported SOP Class UID: {sop_class_uid}")
            continue
        # Create a presentation context for the SOP Class
        context = build_context(sop_class)
        # Associate with the peer AE
        assoc = ae.associate(ip, port, contexts=[context], ae_title=pacs_ae_title)
        
        if assoc.is_established:
            for info in item["sop_instance_infos"]:
                file_path = info["path"]
                ds = dcmread(file_path)
                now = datetime.now()
                date_int_str = now.strftime('%Y%m%d')
                time_int_str = now.strftime("%H%M%S")
                ds.InstanceCreationDate = date_int_str
                ds.InstanceCreationTime = time_int_str
                ds.SOPInstanceUID = info["sop_instance_uid"]
                ds.PatientName = patient_data["PatientName"]
                ds.PatientID = patient_data["PatientID"]
                ds.PatientBirthDate = patient_data["PatientBirthDate"]
                ds.PatientSex = patient_data["PatientSex"]
                ds.StudyInstanceUID = patient_data["StudyInstanceUID"]
                ds.SeriesInstanceUID = item["SOPClassUID"]
                status = assoc.send_c_store(ds)
                # Check the status of the storage request
                if status:
                    print(f'C-STORE request status for {file_path}: SUCCESS')
                else:
                    print(f'Connection timed out, was aborted or received invalid response for {file_path}')
            assoc.release()
        else:
            print(f'Association rejected, aborted or never connected for SOP Class UID: {sop_class_uid} ip: {ip} port: {port}') 
