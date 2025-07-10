# Autocomper

Autocomper is a GUI frontend for `sound_reader.py`: a useful script that takes in videos, extracts <em>certain</em> portions from them, and writes the result to a new video.

## Using the Program

1. [Install a release](https://github.com/0-bff/autocomper/releases) or [build and run](#building) the program for your platform.

2. Click `"Add Videos"`, then select any number of videos.
   - If you are combining the videos, you can change the order of their appearance in the final video by selecting a video in the list, then using the up/down arrows.
   - You can remove unwanted videos by selecting one or multiple videos from the list, then hitting `"Remove Selected"`. You can also hit `"Clear All"` to remove all the videos at once.

3. Set the `precision`, `block size`, and `threshold`, and turn on any miscellaneous options. You can hover over each of the boxes to get more information about each parameter.  
   - You can also set the `focus index` to specify the target sound class. Use `58` for burps and `60` for farts. Change this value according to what type of sound you want to isolate in the final video.

4. Click the `"Select Output File"` button in the top right to pick a place to write the final video(s).
   - If you selected `"Combine Input Videos"`, you will select one specific file to write everything to. Otherwise, you will pick a directory, and individual videos will be written as `{original_title}_comped.mp4`.

5. Click "Process Videos" to begin the comping process. Depending on your input, this may take a while, especially when writing the final output video if you selected "Combine Input Videos".

6. Once the completion popup appears, navigate to your selected output location and find your video(s).

## Building

**Python Version: 3.10.11+**

### Windows

Ensure that [Python](https://www.python.org/downloads/windows/) is installed, then open a Powershell window at the root directory and run the following commands (or simply run the `build_windows.ps1` script).
    
    $ python -m venv .env
    $ .\.env\Scripts\Activate.ps1
    $ pip install -r requirements.txt
    $ python setup.py build

The executable is written to `build/exe.win-.../autocomper.exe`.

### Linux

Largely the same as Windows. First, ensure that `python3` is installed:

    $ sudo apt-get update
    $ sudo apt-get install python3

Then, open a terminal window at the root directory and run the following commands.

    $ python -m venv .env
    $ source .env/bin/activate
    $ pip install -r requirements.txt
    $ python setup.py build

You can also simply run:
 
    $ ./build_linux

The executable is written to `build/exe.linux-.../autocomper`. If permission is denied, please run the following command from the root directory.

    $ chmod +x build/exe.linux-.../autocomper

### OSX

No Mac build yet. Sorry :(

## TODO

- Figure out how to build the program with `onnxruntime-gpu` instead of having to use boring old `onnxruntime`.
- Add other filetype options for output besides mp4.
- Add multiprocessing to video writing + switch to using raw FFMPEG instead of moviepy for maximum speed
- Add a "model download center" to avoid having to pack models in with the releases
- Add "open output" button on completion
