import ffmpeg
import os
import subprocess
import datetime
import random
import string

from math import ceil


#GLOBAL

CACHE_DIR_NAME = "cache"
CACHED_FILENAME = f"./{CACHE_DIR_NAME}/chunk.mp4"
EXTRACTED_FRAMES_DIR = f"./{CACHE_DIR_NAME}/extracted_frames"
WORK_WITH_FORMATS = {"mp4", "mkv", "avi", "mov", "fly", "webm", "3gp", "3g2", "ogg", "asf", "mxf"}

# FFMPEG VALUES
CHUNK_TIME= datetime.timedelta(seconds=60)
VIDEO_CODEC = "copy"
AUDIO_CODEC = "copy"
TOTAL_THREADS = 32
PIXEL_FORMAT = "yuv420p"

def create_dir(path: str):
    subprocess.run(f"mkdir -p {path}", shell=True)

def remove_dir(path: str):
    os.removedirs(path)

def mount_cache_dir():
    #create ram dir
    # Define the command you want to run with sudo
    command = f"sudo mount -t tmpfs -o size=10G tmpfs ./{CACHE_DIR_NAME}"
    try:
        # Run the command with sudo
        subprocess.run(command, shell=True, check=True)
        #print(f"Successfully mounted tmpfs in {CACHE_DIR_NAME}")
    except Exception as e:
        pass
        # Handle other exceptions
        #print(f"An error occurred: {e}")

def umount_cache_dir():
    command = f"sudo umount ./{CACHE_DIR_NAME}"
    try:
        # Run the command with sudo
        subprocess.run(command, shell=True, check=True)
        #print(f"Successfully mounted tmpfs in {CACHE_DIR_NAME}")
    except Exception as e:
        pass
        # Handle other exceptions
        #print(f"An error occurred: {e}")

def find_all_video_files(directory):
    all_video_files = []

    if os.path.exists(directory):
        if os.path.isfile(directory):
            if directory.split(".")[-1].lower() in WORK_WITH_FORMATS:
                all_video_files.append(directory)
        elif os.path.isdir(directory):
            for root, _, files in os.walk(directory):
                for filename in files:
                    if filename.split(".")[-1].lower() in WORK_WITH_FORMATS:
                        all_video_files.append(os.path.join(root, filename))

    return all_video_files

def clear_cache(directory_path) -> None:
    # Iterate through all items in the directory
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)

        if os.path.isfile(item_path):
            # If it's a file, remove it
            os.remove(item_path)
        elif os.path.isdir(item_path):
            # If it's a directory, remove it recursively
            clear_cache(item_path)


def extract_main_info_about_video(filename):
    info_about_file = dict()
    info_about_file["FILENAME"] = filename
    probe = ffmpeg.probe(filename)
    info_about_file['TOTAL_TIME'] = datetime.timedelta(seconds=ceil(float(probe['format']['duration'])))
    frame_date = [int(value) for value in  probe["streams"][0]["avg_frame_rate"].split("/")]
    info_about_file['FRAME_RATE'] = frame_date[0]/ frame_date[1]
    info_about_file['HEIGHT'] = probe['streams'][0]['coded_height']
    info_about_file['WIDTH'] = probe['streams'][0]['coded_width']
    info_about_file['START_TIME'] = datetime.timedelta(0)
    info_about_file['CURRENT_CHUNK'] = 1
    info_about_file['CHUNKS_NAMES'] = []
    return info_about_file

name_mapping = {}

def generate_simple_name(original_name):
    # Check if the original name already has a generated name
    if original_name in name_mapping:
        return name_mapping[original_name]

    # Generate a random simple name
    simple_name = ''.join(random.choice(string.ascii_letters) for _ in range(8))

    # Store the mapping in the dictionary
    name_mapping[original_name] = simple_name

    return simple_name

def restore_original_name(simple_name):
    # Check if the simple name exists in the mapping
    for original_name, mapped_name in name_mapping.items():
        if mapped_name == simple_name:
            return original_name

    # If the simple name is not found, return None
    return None

def extract_frames():
    # input_video = CACHED_FILENAME
    create_dir(EXTRACTED_FRAMES_DIR)
    # output_pattern = f'{EXTRACTED_FRAMES_DIR}/frame%08d.png'
    # ffmpeg.input(input_video).output(output_pattern, crf=1).run()
    command = f"ffmpeg -i {CACHED_FILENAME} -qscale:v 1 -qmin 1 -qmax 1 -fps_mode passthrough -thread_queue_size {TOTAL_THREADS} {EXTRACTED_FRAMES_DIR}/frame%08d.png "
    subprocess.run(command, shell=True,  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(command)

def calculate_upscale_ratio(height, width):
    allowed_upscale_factors = (1, 2, 4, 8, 8, 32)

    for factor in allowed_upscale_factors:
        upscaled_height = height * factor
        upscaled_width = width * factor
        if upscaled_height >= 2160 and upscaled_width >= 3840:
            return f"-s {factor}"

    return None  # Return None if no upscale factor meets the criteria


def create_chunk(filename,
                 start_time,
                 chunk_time,
                 video_codec,
                 audio_codec,
                 output_filename,
                 file_info,
                 threads=TOTAL_THREADS):
    command = f'ffmpeg -ss {start_time} -i {filename} -t {chunk_time} -c:v {video_codec} -c:a aac -b:a 192k -q:a 1 -q:v 1 -thread_queue_size {threads} -fps_mode passthrough {output_filename}'
    print(command)
    subprocess.run(command, shell=True, check=True)




def upscale_frames_by_waifu2x(file_info,
                              path="./waifu2x-ncnn-vulkan",
                              input_path="-i ./cache/extracted_frames",
                              output_path="-o ./cache/upscaled_frames",
                              noise_level="-n 2",
                              scale="-s 4",
                              tile_size="-t 400,400,400",
                              model_path="-m models-upconv_7_anime_style_art_rgb",
                              gpu_id="-g -1,0,1",
                              thread_count="-j 8:8:8,8:8:8,8:8:8",
                              tta_mode="",
                              format="-f png"):
        create_dir(f"./{CACHE_DIR_NAME}/upscaled_frames")
        command = f"{path} {input_path} {output_path} {noise_level} {scale} {tile_size} {gpu_id if gpu_id is not None else ''} {thread_count if thread_count is not None else ''} {tta_mode if tta_mode is not None else ''} {model_path} {format}"
        subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(command)



def combine_frames(file_info,
                   frame_rate,
                   video_codec=VIDEO_CODEC,
                   audio_codec=AUDIO_CODEC,
                   pix_fmt=PIXEL_FORMAT,
                   threads=TOTAL_THREADS,):
    chunk = file_info["CURRENT_CHUNK"]
    command = f'ffmpeg -r {frame_rate} -i ./cache/upscaled_frames/frame%08d.png -i ./cache/chunk.mp4 -map 0:v:0 -map 1:a:0 -c:a {audio_codec} -c:v hevc_nvenc -r {frame_rate} -pix_fmt {pix_fmt} -thread_queue_size {threads} chunk_{chunk:05d}.mp4'
    subprocess.run(command, check=True, shell=True) # -vf "scale={int(file_info["WIDTH"])* 4}:{int(file_info["HEIGHT"]) * 4}"
    file_info['START_TIME'] += CHUNK_TIME
    file_info['CURRENT_CHUNK'] += 1
    file_info['CHUNKS_NAMES'].append(f"file chunk_{chunk:05d}\n")

def rename_file(file_info):
    new_filename = generate_simple_name(file_info['FILENAME'])
    subprocess.run(f'mv {file_info["FILENAME"]} {new_filename}', shell=True, check=True)


def  rename_file_back(file_info):
    old_filename = restore_original_name(file_info['FILENAME'])
    subprocess.run(f'mv {file_info["FILENAME"]} {old_filename}', shell=True, check=True)



def combine_video_files(file_info):
    subprocess.run("ls -1 chunk_* | sed 's/^/file /' > chunks.txt", shell=True)
    command = f"ffmpeg -f concat -safe 0 -i chunks.txt   UPSCALED_{file_info['FILENAME']}"
    subprocess.run(command, shell=True)
    subprocess.run("rm $(ls -1 chunk_*)", check=True, shell=True)


def main():
    create_dir(CACHE_DIR_NAME)
    mount_cache_dir()
    all_video_files = find_all_video_files(input("Please Enter Path to Video Files:\n"))
    while all_video_files:
        file_info = extract_main_info_about_video(all_video_files.pop(0))
        rename_file(file_info)
        # upscale_raito = calculate_upscale_ratio(file_info['HEIGHT'], file_info['WIDTH']) if not None else "-s 4"
        while file_info['START_TIME'] < file_info['TOTAL_TIME']:
            create_chunk(filename=file_info['FILENAME'],
                         start_time=file_info["START_TIME"],
                         chunk_time=CHUNK_TIME,
                         video_codec=VIDEO_CODEC,
                         audio_codec=AUDIO_CODEC,
                         output_filename=CACHED_FILENAME,
                         file_info=file_info
                         )
            extract_frames()
            upscale_frames_by_waifu2x(file_info)
            combine_frames(file_info,
                           file_info['FRAME_RATE'])
            clear_cache(CACHE_DIR_NAME)
        rename_file_back(file_info)
        combine_video_files(file_info)
    umount_cache_dir()
    remove_dir(CACHE_DIR_NAME)

if __name__ == "__main__":
    main()


