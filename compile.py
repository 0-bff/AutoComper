#!/usr/bin/env python
import os
import tempfile
from math import floor
from shutil import move

# Atlas version fix
from PIL import Image
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from colorama import Fore, Style

from moviepy.audio.fx.audio_normalize import audio_normalize
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips
from moviepy.video.fx.margin import margin
from moviepy.video.fx.resize import resize

MERGE_THRESHOLD = 2  # seconds
BATCH_SIZE = 10


def compile_vid(dict_list, output, merge_clips=True, combine_vids=True, res=None, logger=None, normalize=False, is_video=True, padding=None):
    output_format = ".mp4" if is_video else ".mp3"
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            tempfiles = []
            curr = None
            for n, elt in enumerate(dict_list):
                filename = elt["filename"]
                filename_stripped = os.path.basename(str(elt["filename"]))
                timestamps = [(d["start"], d["end"])
                              for d in elt["timestamps"]]

                print(
                    f"{Fore.GREEN}[{n + 1}/{len(dict_list)}]{Style.RESET_ALL} Writing all clips for {filename_stripped}...", end="")

                clips = []

                try:
                    curr = VideoFileClip(
                        filename) if is_video else AudioFileClip(filename)
                except Exception as e:
                    print(f"{Fore.RED}Problem reading input video! Continuing...")
                    continue

                if padding:
                    before, after = padding
                    if before < 0 or after < 0:
                        raise Exception(
                            "Clip padding cannot be a negative number!")
                    for i, ts in enumerate(timestamps):
                        timestamps[i] = (ts[0] - before, ts[1] + after)

                if merge_clips:
                    i = 0
                    while i < len(timestamps) - 1:
                        if timestamps[i + 1][0] - timestamps[i][1] < MERGE_THRESHOLD:
                            timestamps[i] = (timestamps[i][0],
                                             timestamps[i + 1][1])
                            timestamps.remove(timestamps[i + 1])
                        else:
                            i += 1

                if not timestamps:
                    print(f"{Fore.YELLOW}No timestamps found for this video!")
                    continue

                for i, ts in enumerate(timestamps):
                    ts_start = max(ts[0], 0)
                    ts_end = min(ts[1], curr.duration)
                    clip = curr.subclip(ts_start, ts_end)
                    clips.append(clip)

                if combine_vids:
                    temp = temp_dir + str(n) + output_format
                    tempfiles.append(temp)
                else:
                    temp = str(filename.split('/')[-1]).rsplit('.', 1)
                    temp = '.'.join(temp[:-1])
                    temp = str(output + '/' + temp + "_comped" + output_format)

                if is_video:
                    final = concatenate_videoclips(clips, method="chain")
                else:
                    final = concatenate_audioclips(clips)

                # Resize clips if not combining but using a custom res
                # Note: we do not resize if we are combining since we can just do it on a
                # per-video basis instead of a per-clip basis
                if is_video and not combine_vids and res is not None:
                    w2, h2 = res
                    w1, h1 = final.size
                    ratio = min(w2/w1, h2/h1)
                    new_size = tuple([floor(ratio*x) for x in final.size])

                    final = resize(
                        final, width=new_size[0], height=new_size[1])
                    horiz_margin = max(abs((res[0] - new_size[0])), 0)
                    vert_margin = max(abs((res[1] - new_size[1])), 0)

                    horiz_margin = [horiz_margin, horiz_margin]
                    if horiz_margin[0] % 2 == 1:
                        horiz_margin[0] += 1

                    horiz_margin = [int(x / 2) for x in horiz_margin]

                    vert_margin = [vert_margin, vert_margin]
                    if vert_margin[0] % 2 == 1:
                        vert_margin[0] += 1

                    vert_margin = [int(x / 2) for x in vert_margin]

                    final = margin(
                        final, left=horiz_margin[0], right=horiz_margin[1], top=vert_margin[0], bottom=vert_margin[1])

                # Very jank normalization that barely does anything
                if normalize:
                    audio = final.audio.set_fps(44100)
                    normalized_audio = audio_normalize(audio)
                    final = final.set_audio(normalized_audio)

                if is_video:
                    final.write_videofile(
                        temp, logger=logger, codec='libx264', audio=True)
                else:
                    final.write_audiofile(temp, logger=logger)

                for clip in clips:
                    clip.close()
                curr.close()
                final.close()

                print(f"{Fore.GREEN}Done writing all clips for {filename_stripped}.")

            if combine_vids:
                print(
                    "Combining individual media, please do not close the program...", end="")

                if len(tempfiles) == 0:
                    raise (Exception("No timestamps found for any input media!"))

                clips = []
                sizes = []
                for i, file in enumerate(tempfiles):
                    clip = VideoFileClip(
                        file) if is_video else AudioFileClip(file)
                    clips.append(clip)
                    if is_video:
                        sizes.append(clip.size)

                # Resize all clips based on the size of the largest sized clip OR the requested custom resolution
                # Largest total area; in ties, prioritize larger width over larger height (ex. 1920 x 1080 > 1080 x 1920)
                if is_video:
                    if res is not None:
                        max_size = res
                    else:
                        # No custom res + only comping one file means
                        # we can just move it from the temp directory to the real output
                        if len(tempfiles) == 1:
                            for clip in clips:
                                clip.close()
                            move(tempfiles[0], output)
                            del tempfiles[0]
                            return

                        max_size = max(sorted(sizes, key=lambda x: x[0])[
                            ::-1], key=lambda x: x[0] * x[1])

                    w2, h2 = max_size
                    new_sizes = []
                    for size in sizes:
                        w1, h1 = size
                        ratio = min(w2/w1, h2/h1)
                        new_sizes.append(tuple([floor(ratio*x) for x in size]))

                    for i, clip in enumerate(clips):
                        clips[i] = resize(clip, width=new_sizes[i]
                                          [0], height=new_sizes[i][1])
                        horiz_margin = max(
                            abs(int((max_size[0] - new_sizes[i][0]))), 0)
                        vert_margin = max(
                            abs(int((max_size[1] - new_sizes[i][1]))), 0)

                        horiz_margin = [horiz_margin, horiz_margin]
                        if horiz_margin[0] % 2 == 1:
                            horiz_margin[0] += 1

                        horiz_margin = [int(x / 2) for x in horiz_margin]

                        vert_margin = [vert_margin, vert_margin]
                        if vert_margin[0] % 2 == 1:
                            vert_margin[0] += 1

                        vert_margin = [int(x / 2) for x in vert_margin]

                        clips[i] = margin(
                            clips[i], left=horiz_margin[0], right=horiz_margin[1], top=vert_margin[0], bottom=vert_margin[1])

                if is_video:
                    final = concatenate_videoclips(clips, method="compose")
                    final.write_videofile(
                        output, codec='libx264', audio=True, logger=logger)
                else:
                    final = concatenate_audioclips(clips)
                    final.write_audiofile(
                        output, logger=logger)

                for clip in clips:
                    clip.close()

                final.close()

                print(f"{Fore.GREEN}Done combining media.")
    except Exception as e:
        raise (Exception(str(e)))

    finally:
        if clips:
            for clip in clips:
                clip.close()

        if curr:
            curr.close()

        for file in tempfiles:
            try:
                os.remove(file)
            except FileNotFoundError:
                continue
