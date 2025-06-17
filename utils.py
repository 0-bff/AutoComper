import sys
import os
import platform
import shutil
import re
from pathlib import Path

from typing import Literal, Tuple, Dict, Any, Optional, List

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from yt_dlp.networking.exceptions import TransportError

DOWNLOAD_QUALITY_OPTIONS = ["No Limit", "144p", "240p", "360p",
                            "480p", "720p", "1080p", "1440p", "2160p", "4320p"]


def get_bundle_filepath(filepath: str) -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_dir = str(sys._MEIPASS)
        return os.path.join(Path.cwd(), bundle_dir, filepath)
    else:
        return os.path.join(Path.cwd(), filepath)


current_platform = platform.system()
if current_platform == "Windows":
    ffmpeg_path = r".\ffmpeg\windows\ffmpeg.exe"
    is_windows = True
elif current_platform == "Darwin":  # macOS
    ffmpeg_path = r"./ffmpeg/osx/ffmpeg"
else:  # Linux
    ffmpeg_path = r"./ffmpeg/linux/ffmpeg"

FFMPEG_PATH = get_bundle_filepath(ffmpeg_path)


def convert_quality_str_to_int(quality: str) -> int:
    if not quality:
        return None

    numbers = re.findall(r'\d+', quality)

    if len(numbers) == 1:
        # Case like '720p' where there is only one number
        return int(numbers[0])
    elif len(numbers) == 2:
        # Case like '256x144' where there are two numbers; return the greater number
        return min(tuple(map(int, numbers)))
    else:
        return None


def get_single_video_details(url, max_quality: str):
    max_height = convert_quality_str_to_int(max_quality)

    format_str = \
        f'bestvideo[height<={max_height}]+bestaudio/bestvideo[height<=720][fps<=60]+bestaudio/bestvideo[height<={max_height}]/best[height<={max_height}]' \
        if max_quality in DOWNLOAD_QUALITY_OPTIONS and max_quality != DOWNLOAD_QUALITY_OPTIONS[0] else 'bestvideo+bestaudio/best'

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'format': format_str,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)

    if info_dict is not None \
            and info_dict.get('title') not in [None, "[Private video]", "[Deleted video]"] \
            and (info_dict.get('uploader')) \
            and (info_dict.get('original_url') or info_dict.get('url')):
        return {
            'id': info_dict.get('id'),
            'title': info_dict.get('title'),
            'uploader': info_dict.get('uploader'),
            'url': info_dict.get('original_url') or info_dict.get('url'),
        }
    return None


def get_urls(base_url: str):
    def check_video(info_dict):
        if not info_dict.get('entries'):
            return [info_dict.get('original_url') or info_dict.get('url')]
        else:
            return [check_video(x) for x in info_dict['entries']]

    def flatten(nested_list):
        for item in nested_list:
            if isinstance(item, list):
                yield from flatten(item)
            else:
                yield item

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',  # Extract only metadata, not the video itself
    }
    while True:
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(base_url, download=False)
                break
        except TransportError:
            continue
        except Exception:
            raise

    return list(flatten(check_video(info_dict)))


def get_number_of_vids_in_playlist(playlist_url: str) -> int:
    try:
        return len(get_urls(playlist_url))
    except:
        raise


def is_valid_yt_dlp_url(base_url: str, max_quality: str = None):
    if max_quality and max_quality not in DOWNLOAD_QUALITY_OPTIONS:
        raise Exception("Invalid max quality specified")

    try:
        urls = get_urls(base_url)
    except DownloadError as e:
        cleaned_error = '.'.join(str(e).split(':')[1:])
        raise Exception(
            f"An error occured while retrieving URLs: {str(cleaned_error)}")
    except Exception as e:
        raise Exception(
            f"An unexpected error occured while retrieving URLs. Please try again.\nError: {str(e)}")

    for url in urls:
        try:
            vid_details = get_single_video_details(url, max_quality)
            if vid_details:
                yield vid_details
            else:
                yield Exception("Video is privated, deleted, or otherwise unavailable.\nIf you know the video is public, try raising your max allowed quality in settings.")
        except DownloadError as e:
            cleaned_error = '.'.join(str(e).split(':')[1:])
            if 'Requested format' in cleaned_error:
                yield Exception("No video found at or below the max allowable quality.\nTry raising your max quality in settings.")
            else:
                yield Exception(
                    f"An error occured while retrieving URLs: {str(cleaned_error)}")
        except Exception as e:
            yield Exception(
                f"An unexpected error occured while retrieving URLs. Please try again.\nError: {str(e)}")


def download_video(url: str, filename: str, output_location: str, max_quality: str, max_speed: int, logger, n_retries: int = 3) -> Tuple[bool, str]:
    logger.reset_total_progress(100)
    os.makedirs(output_location, exist_ok=True)

    max_height = convert_quality_str_to_int(max_quality)

    format_str = \
        f'bestvideo[height<={max_height}]+bestaudio/bestvideo[height<=720][fps<=60]+bestaudio/bestvideo[height<={max_height}]/best[height<={max_height}]' \
        if max_quality in DOWNLOAD_QUALITY_OPTIONS and max_quality != DOWNLOAD_QUALITY_OPTIONS[0] else 'bestvideo+bestaudio/best'

    ydl_opts = {
        'outtmpl': f"{filename}.%(ext)s",
        'format': format_str,
        'quiet': True,
        'logger': logger,
        'progress_hooks': [logger.hook],
        'ffmpeg_location': FFMPEG_PATH
    }
    
    if max_speed > 0:
        ydl_opts['limit_rate'] = f"{max_speed}K"

    with open(os.devnull, 'w') as devnull:
        attempts = 0
        while attempts < n_retries:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = devnull
            sys.stderr = devnull

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    # Check if there is any valid video
                    # There are cases where we need to skip instead of stopping, e.x. TikTok photo slideshows
                    video_info = ydl.extract_info(url, download=False)

                    has_video = any(
                        (fmt.get('vcodec') != 'none' and fmt.get(
                            'acodec') != 'none')
                        or
                        (fmt.get('video_ext') != 'none' and fmt.get(
                            'audio_ext') != 'none')
                        for fmt in video_info.get('formats', [])
                    ) or (
                        video_info.get('vcodec') and video_info.get(
                            'vcodec') != 'none'
                    )

                    if not has_video:
                        return True, None

                    info_dict = ydl.extract_info(url, download=True)

                file_ext = info_dict.get('ext', 'mp4')
                output_file = os.path.join(
                    output_location, f"{filename}.{file_ext}")
                shutil.move(f"{filename}.{file_ext}", output_file)
                return True, output_file
            except Exception as e:
                attempts += 1
                if attempts >= n_retries:
                    return False, str(e)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr


def download_audio(url: str, filename: str, output_location: str, max_speed: int, logger, n_retries: int = 10) -> Tuple[bool, str]:
    logger.reset_total_progress(100)

    os.makedirs(output_location, exist_ok=True)
    ydl_opts = {
        'outtmpl': f"{filename}.%(ext)s",
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'progress_hooks': [logger.hook],
        'ffmpeg_location': FFMPEG_PATH
    }
    
    if max_speed > 0:
        ydl_opts['limit_rate'] = f"{max_speed}K"

    with open(os.devnull, 'w') as devnull:
        attempts = 0
        while attempts < n_retries:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = devnull
            sys.stderr = devnull

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    file_ext = ydl.params['postprocessors'][0].get(
                        'preferredcodec', info_dict.get('ext', 'mp3'))
                    output_file = os.path.join(
                        output_location, f"{filename}.{file_ext}")
                    shutil.move(f"{filename}.{file_ext}", output_file)
                    return True, output_file
            except Exception as e:
                attempts += 1
                if attempts >= n_retries:
                    return False, str(e).encode("utf-8")
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr


class MediaUpload:
    def __init__(self, path: str, type: Literal['video', 'audio'], is_url: bool = False, url: Optional[str] = None):
        self.path = path
        self.type = type
        self.is_url = is_url
        self.url = url

    def get_path(self) -> str:
        return self.path

    def set_path(self, path: str):
        self.path = path

    def get_type(self) -> Literal['video', 'audio']:
        return self.type

    def set_type(self, type: Literal['video', 'audio']):
        self.type = type

    def get_is_url(self) -> bool:
        return self.is_url

    def set_is_url(self, is_url: bool):
        self.is_url = is_url

    def get_url(self) -> Optional[str]:
        return self.url
