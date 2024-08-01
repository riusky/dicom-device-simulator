import os
import json

def get_files_in_directory(directory_path):
    if not os.path.exists(directory_path):
        print(f"The directory {directory_path} does not exist.")
        return []
    
    if not os.path.isdir(directory_path):
        print(f"The path {directory_path} is not a directory.")
        return []
    
    files = []
    for entry in os.listdir(directory_path):
        entry_path = os.path.join(directory_path, entry)
        if os.path.isfile(entry_path):
            files.append(entry)
    
    return files

def ensure_directory_exists(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

def json_file_exists(file_path):
    return os.path.isfile(file_path)

def read_json_file(file_path):
    if json_file_exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        print(f"File {file_path} does not exist.")
        return None

def write_json_file(file_path, data):
    ensure_directory_exists(file_path)
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def update_json_file(file_path, new_data):
    if json_file_exists(file_path):
        with open(file_path, 'r+', encoding='utf-8') as file:
            data = json.load(file)
            data.update(new_data)
            file.seek(0)
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.truncate()
    else:
        print(f"File {file_path} does not exist. Creating a new file.")
        write_json_file(file_path, new_data)

def delete_json_file_content(file_path):
    if json_file_exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write('{}')
    else:
        print(f"File {file_path} does not exist.")
        
if __name__ == "__main__":
    filenames = get_files_in_directory('./data_base/mpps')
    print(filenames)