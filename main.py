import os
import subprocess
import shutil
import sys
import re
import json


def load_config(filepath):
    config = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.split('//')[0].strip()
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if value.isdigit():
                    value = int(value)
                else:
                    try:
                        value = float(value)
                    except ValueError:
                        pass  # keep as string if not number
                config[key] = value
    return config
            

MOVIES_DIR = "movies"
OUTPUT_MOVIES_DIR = "F:/output/movies"
ADS_DIR = "ads"
WELCOME_TEXT_FILE = "welcome.txt"
TEMP_DIR = "F:/temp_movie_folder"
FFMPEG_COMMON_VIDEO = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18']
FFMPEG_COMMON_AUDIO = ['-c:a', 'aac', '-b:a', '320k']
FFMPEG_SCALE = ['-vf', 'scale=1280:720']
WHOLE_MOVIE_TEXT_FILE = "wholeMovieText.txt"
TEXT_SIZE=36

def generate_welcome_video(output_path):
    print(f"Generating welcome video at: {output_path}")
    
    if not os.path.exists(WELCOME_TEXT_FILE):
        print(f"{WELCOME_TEXT_FILE} not found. Skipping welcome video generation.")
        return None

    with open(WELCOME_TEXT_FILE, 'r', encoding='utf-8') as f:
        lines = [
            line.split('//')[0].strip().replace(":", r'\:').replace("'", r"\'")
            for line in f if line.strip() and not line.strip().startswith('//')
        ]

    if not lines:
        print(f"{WELCOME_TEXT_FILE} is empty or contains no valid lines. Skipping welcome video generation.")
        return None

    # Text layout setup
    line_h = WELCOME_VIDEO_TEXT_SIZE + 10
    background_width = 800
    background_height = 300
    border_thickness = 3  # Visible border
    background_color = 'blue@0.7'

    drawtext_filters = []

    video_width = 1280
    video_height = 720

    # Calculate center positions for background
    bg_x_value = (video_width - background_width) / 2
    bg_y_value = (video_height - background_height) / 2

    bg_x = str(int(bg_x_value))
    bg_y = str(int(bg_y_value))

    print(f"bg_x value is: {bg_x}")
    print(f"bg_y value is: {bg_y}")

    # 1. Draw white border
    drawbox_border = (
        f"drawbox=x='({bg_x})-{border_thickness}':"
        f"y='({bg_y})-{border_thickness}':"
        f"w={background_width + 2 * border_thickness}:"
        f"h={background_height + 2 * border_thickness}:"
        f"color=white:t=fill"
    )

    # 2. Draw blue background
    drawbox_bg = (
        f"drawbox=x='{bg_x}':"
        f"y='{bg_y}':"
        f"w={background_width}:"
        f"h={background_height}:"
        f"color={background_color}:t=fill"
    )

    drawtext_filters.extend([drawbox_border, drawbox_bg])

    # 3. Draw centered text
    for idx, line in enumerate(lines):
        total_text_height = len(lines) * line_h
        text_start_y = f"{bg_y}+({background_height}-{total_text_height})/2+{idx}*{line_h}"

        drawtext = (
            f"drawtext=fontfile='C\\:/Windows/Fonts/times.ttf':"
            f"text='{line}':fontcolor=white:fontsize={WELCOME_VIDEO_TEXT_SIZE}:"
            f"x='(w-text_w)/2':"
            f"y='{text_start_y}':"
            f"box=0"
        )
        drawtext_filters.append(drawtext)

    full_filter = ",".join(drawtext_filters)
    print("Using FFmpeg filter:", full_filter)

    subprocess.run([
        'ffmpeg', '-f', 'lavfi', '-i', f'color=c=black:s={video_width}x{video_height}:d={WELCOME_VIDEO_DURATION}',
        '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
        '-vf', full_filter,
        '-shortest',
        *FFMPEG_COMMON_VIDEO,
        *FFMPEG_COMMON_AUDIO,
        '-y', output_path
    ])

    print("Welcome video generation completed.")
    return output_path


def has_audio_stream(input_path):
    result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=index',
        '-of', 'json',
        input_path
    ], capture_output=True, text=True)
    info = json.loads(result.stdout)
    return len(info.get('streams', [])) > 0

def transcode_to_match(input_path, output_path):
    if has_audio_stream(input_path):
        print(f"Transcoding {input_path} (audio present)")
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-map', '0:v:0',
            '-map', '0:a:0',
            '-shortest',
            *FFMPEG_COMMON_VIDEO,
            *FFMPEG_COMMON_AUDIO,
            *FFMPEG_SCALE,
            '-y', output_path
        ])
    else:
        print(f"Transcoding {input_path} (adding silent audio)")
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',
            *FFMPEG_COMMON_VIDEO,
            *FFMPEG_COMMON_AUDIO,
            *FFMPEG_SCALE,
            '-y', output_path
        ])

def split_movie(movie_path, output_dir):
    print(f"Splitting movie: {movie_path} into chunks.")
    subprocess.run([
        'ffmpeg', '-i', movie_path,
        *FFMPEG_COMMON_VIDEO,
        *FFMPEG_COMMON_AUDIO,
        *FFMPEG_SCALE,
        '-f', 'segment', '-segment_time', str(ADS_INBETWEEN_MOVIES_TIME),
        '-reset_timestamps', '1',
        os.path.join(output_dir, 'chunk_%03d.mkv')
    ])
    print(f"Movie split completed. Chunks saved in: {output_dir}")

def get_ads(n, temp_dir):
    print(f"Fetching {n} ads from: {ADS_DIR}")

    if not os.path.exists(ADS_DIR):
        print(f"Ads folder '{ADS_DIR}' does not exist. Skipping ads.")
        return []

    ads = sorted([f for f in os.listdir(ADS_DIR) if f.endswith('.mp4')])

    if not ads:
        print(f"No ad files found in '{ADS_DIR}'. Skipping ads.")
        return []
    
    selected_ads = (ads * ((n + len(ads) - 1) // len(ads)))[:n]
    result_ads = []

    for i, ad in enumerate(selected_ads):
        ad_input = os.path.join(ADS_DIR, ad)
        ad_transcoded = os.path.join(temp_dir, f'ad_{i:03d}.mkv')
        transcode_to_match(ad_input, ad_transcoded)
        result_ads.append(ad_transcoded)

    print(f"Prepared ads: {result_ads}")
    return result_ads


def process_movie(movie_path, output_dir):
    print(f"Processing movie: {movie_path}")
    os.makedirs(TEMP_DIR, exist_ok=True)

    welcome_video_path = os.path.join(TEMP_DIR, 'welcome.mkv')
    welcome_video_generated = generate_welcome_video(welcome_video_path)
    print(f"welcome_video_generated movie: {welcome_video_generated}")
    
    split_movie(movie_path, TEMP_DIR)
    chunks = sorted([f for f in os.listdir(TEMP_DIR) if f.startswith('chunk')])
    chunks = [os.path.join(TEMP_DIR, chunk) for chunk in chunks]
    print(f"Chunks generated: {chunks}")
    
    all_parts = []
    if welcome_video_generated:
        all_parts.append(welcome_video_generated)
        
    ads = get_ads(len(chunks) - 1, TEMP_DIR)         

    
    interleaved_parts = []
    for i, chunk in enumerate(chunks):
        overlay_chunk = os.path.join(TEMP_DIR, f'chunk_with_countdown_{i:03d}.mkv')

        probe_result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            chunk
        ], capture_output=True, text=True)

        chunk_duration = float(probe_result.stdout.strip())  # seconds
        print(f"Chunk {i} duration: {chunk_duration} seconds")
        countdown_start_time = chunk_duration - 5  # Start countdown 5 seconds before end
        countdown_duration = 5
        countdown_text = (
        "drawtext=fontfile='C\\:/Windows/Fonts/times.ttf':"
        f"text='Ads in %{{eif\\:{countdown_duration}-(t-{countdown_start_time})\\:d}}s':"
        f"fontcolor=white:fontsize={TEXT_SIZE}:"
        "x=(w - text_w - 20):y=(h - 100):"
        f"enable='gte(t,{countdown_start_time})':"
        f"shadowx=3:shadowy=3:shadowcolor=black"
        )

        subprocess.run([
        'ffmpeg', '-i', chunk,
        '-vf', countdown_text,
        *FFMPEG_COMMON_VIDEO, *FFMPEG_COMMON_AUDIO,
        '-y', overlay_chunk
        ])
        interleaved_parts.append(overlay_chunk)

        if ads:    
            if i < len(ads):
             interleaved_parts.append(ads[i])

    all_parts += interleaved_parts  # add other parts as usual

     
    print(f"all_parts list is: {all_parts}")
    
    file_list = os.path.join(TEMP_DIR, 'file_list.txt')
    with open(file_list, 'w') as f:
        for part in all_parts:
            abs_path = os.path.abspath(part).replace('\\', '/')
            f.write(f"file '{abs_path}'\n")
    print(f"File list for concatenation created at: {file_list}")
    
    final_output_path = os.path.join(output_dir, os.path.splitext(os.path.basename(movie_path))[0] + '.mkv')
    
    intermediate_path = final_output_path.replace('.mkv', '_intermediate.mkv')
    os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

    if os.path.exists(final_output_path):
        os.remove(final_output_path)
    if os.path.exists(intermediate_path):
        os.remove(intermediate_path)

    #file_list = os.path.join(TEMP_DIR, 'file_list.txt')

    print(f"Starting intermediate concat to: {intermediate_path}")
    subprocess.run([
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', file_list,
        '-c', 'copy', '-y', intermediate_path
    ])

    movie_lines = []
    overlay_filter = None  # initialize to avoid UnboundLocalError
    
    if not os.path.exists(WHOLE_MOVIE_TEXT_FILE):
        print(f"{WHOLE_MOVIE_TEXT_FILE} not found. Skipping overlay text.")
    else:
        with open(WHOLE_MOVIE_TEXT_FILE, 'r', encoding='utf-8') as f:
            movie_lines = [
                line.split('//')[0].strip().replace(":", r'\:').replace("'", r"\'")
                for line in f if line.strip() and not line.strip().startswith('//')
            ]
        print(f"{movie_lines} movie value is.")    
        if movie_lines:
            movie_lines = movie_lines[:2]  # Use up to 2 lines
            drawtext_filters = []

            if len(movie_lines) >= 1:
                # First line: Top-left corner
                drawtext_left = (
                    f"drawtext=fontfile='C\\:/Windows/Fonts/times.ttf':"
                    f"text='{movie_lines[0]}':fontcolor=white:fontsize={OPERATOR_PHONE_DISPLAY_TEXT_SIZE}:"
                    f"x=10:y=10:"
                    f"shadowx=3:shadowy=3:shadowcolor=black"
                )
                drawtext_filters.append(drawtext_left)

            if len(movie_lines) >= 2:
                # Second line: Top-right corner
                drawtext_right = (
                    f"drawtext=fontfile='C\\:/Windows/Fonts/times.ttf':"
                    f"text='{movie_lines[1]}':fontcolor=white:fontsize={OPERATOR_PHONE_DISPLAY_TEXT_SIZE}:"
                    f"x=w-text_w-10:y=10:"
                    f"shadowx=3:shadowy=3:shadowcolor=black"
                )
                drawtext_filters.append(drawtext_right)

            overlay_filter = ",".join(drawtext_filters)          
        
    print(f"Re-encoding intermediate file to final output: {final_output_path}")

    ffmpeg_cmd = [
        'ffmpeg', '-i', intermediate_path,
        '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '320k', '-preset', 'medium', '-crf', '18',
        '-y', final_output_path
    ]

    if overlay_filter:
        ffmpeg_cmd.insert(3, '-vf')
        ffmpeg_cmd.insert(4, overlay_filter)
        
    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    progress_pattern = re.compile(r'frame=\s*(\d+)\s+fps=.*time=([0-9:.]+).*speed=\s*([\d\.]+)')
    log_contents = ""

    for line in process.stdout:
        line = line.strip()
        match = progress_pattern.search(line)
        if match:
            frame, time_str, speed = match.groups()
            sys.stdout.write(f"\r→ Frame: {frame}, Time: {time_str}, Speed: {speed}")
            sys.stdout.flush()
        log_contents += line + '\n'

    print()
    process.wait()

    if "Non-monotonic DTS" in log_contents or "error while decoding" in log_contents:
        print("Warning: FFmpeg encountered timestamp or decoding issues. See log for details.")
    else:
        print("FFmpeg re-encode completed without known warnings.")

    if os.path.exists(intermediate_path):
        os.remove(intermediate_path)

    print(f"Final movie saved at: {final_output_path}")
    print(f"Cleaning up temporary files in: {TEMP_DIR}")
    shutil.rmtree(TEMP_DIR)


def process_movies_in_dir(input_dir, output_dir):
    print(f"Processing all movies in directory: {input_dir}")
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.mkv'):
                movie_path = os.path.join(root, file)
                output_subdir = os.path.join(output_dir, os.path.relpath(root, input_dir))
                os.makedirs(output_subdir, exist_ok=True)
                process_movie(movie_path, output_subdir)

def main():
    print("Starting script...")
    process_movies_in_dir(MOVIES_DIR, OUTPUT_MOVIES_DIR)

if __name__ == '__main__':
    config = load_config('configuration.txt')
    WELCOME_VIDEO_DURATION = config.get('WELCOME_VIDEO_DURATION', 5)
    ADS_INBETWEEN_MOVIES_TIME = config.get('ADS_INBETWEEN_MOVIES_TIME', 20) * 60
    WELCOME_VIDEO_TEXT_SIZE = config.get('WELCOME_VIDEO_TEXT_SIZE', 36) 
    OPERATOR_PHONE_DISPLAY_TEXT_SIZE = config.get('OPERATOR_PHONE_DISPLAY_TEXT_SIZE', 36) 
    main()
