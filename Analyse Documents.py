import os
import sys
import boto3
from PIL import Image
import csv
from time import sleep

    
def downsize_image(input_img, new_folder, long_edge):
    temp_file_path = os.path.join(new_folder, os.path.basename(input_img))
    try:
        with Image.open(input_img) as im:
            img_size = im.size
            img = im
            img.load()
    except(IOError, SyntaxError):
        print(f'  Problem loading {os.path.basename(input_img)}.')
        return
    temp_dimensions = (long_edge,
                       int(long_edge / (max(img_size) / min(img_size))))
    temp_img = img.resize((temp_dimensions[img_size.index(max(img_size))],
                           temp_dimensions[img_size.index(min(img_size))]),
                          resample = Image.HAMMING,
                          reducing_gap = 2.0)
    temp_img.save(temp_file_path,
                  quality = 75)
    
    return temp_file_path

def get_kv_map(input_img):
    with open(input_img, 'rb') as im:
        img = im.read()
    client = boto3.client('textract', region_name='eu-west-2')
    response = client.analyze_document(Document={'Bytes': img},
                                       FeatureTypes=['FORMS'])

    # Get the text blocks.
    blocks = response['Blocks']
    
    # Get key and value maps.
    key_map = {}
    value_map = {}
    block_map = {}
    for block in blocks:
        block_id = block['Id']
        block_map[block_id] = block
        if block['BlockType'] == 'KEY_VALUE_SET':
            if 'KEY' in block['EntityTypes']:
                key_map[block_id] = block
            else:
                value_map[block_id] = block

    return key_map, value_map, block_map

def get_kv_relationship(key_map, value_map, block_map):
    kvs = {}
    for block_id, key_block in key_map.items():
        value_block = find_value_block(key_block, value_map)
        key = get_text(key_block, block_map)
        val = get_text(value_block, block_map)
        kvs[key] = val

    return kvs

def find_value_block(key_block, value_map):
    for relationship in key_block['Relationships']:
        if relationship['Type'] == 'VALUE':
            for value_id in relationship['Ids']:
                value_block = value_map[value_id]
                
    return value_block

def get_text(result, blocks_map):
    text = ''
    if 'Relationships' in result:
        for relationship in result['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    if word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X '    

    return text

def dict_to_csv(file, dict_data, mode):
    csv_dir, file_name = os.path.split(file)
    file, ext = os.path.splitext(file_name)
    csv_file = os.path.join(csv_dir, file + '.csv')

    if mode == '1':
        data = {}
        key_list = ['EMAIL ', 'FIRST NAME ', 'LAST NAME ', 'TELEPHONE ',
                    'ADDRESS ', 'TOWN ', 'COUNTY ', 'POST CODE ', 'DATE ',
                    'EVENT ', 'SITTING ID ', 'PHOTOGRAPHER ']
        for k in key_list:
            try:
                data[k] = dict_data[k]
            except KeyError:
                data[k] = ''
    else:
        data = dict_data

    try:
        with open(csv_file, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerows(data.items())
    except IOError:
        print(f'  Error writing csv for {file_name}')

    return csv_file

def main():
    # Take input and warn if nothing provided.
    files = sys.argv[1:]
    if not files:
        print('No input provided.\n\nPlease drag one or more documents onto '
              'the app.')
        sleep(3)
        return

    # Ask whether to optimise for Customer Details forms.
    print('Please choose your application by typing 1 or 2, then press Enter.'
          '\n\n1. Customer Details forms\n2. Other\n')
    while True:
        mode = input()
        if any([mode == '1',
                mode == '2']):
            break
        else:
            print('\nInvalid input, please try again.\n')

    # Set up temporary folder to store downsized images.
    temp_dir = 'Temp'
    if not os.path.exists(temp_dir):
        os.mkdir(temp_dir)

    # Run analysis on all images provided.
    print('\nAnalysing documents.')
    for f in files:
        # Skip incompatible files.
        if not any([f.casefold().endswith('.jpg'),
                    f.casefold().endswith('.jpeg'),
                    f.casefold().endswith('.png')]):
            print(f'  {os.path.basename(f)} skipped due to incompatible '
                  'filetype.')
            continue
        # Produce downsized temporary file.
        temp_file = downsize_image(f, temp_dir, 1500)
        # Analyse document and write key-value pairs to csv.
        key_map, value_map, block_map = get_kv_map(temp_file)
        kvs = get_kv_relationship(key_map, value_map, block_map)
        csv_file = dict_to_csv(f, kvs, mode)
        # Remove temporary file.
        os.remove(temp_file)
        print(f'  {os.path.basename(csv_file)} saved.') 

    input('\nAnalysis complete. Press Enter to close.')
        

if __name__ == '__main__':
    main()

