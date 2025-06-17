import sys
from cx_Freeze import setup, Executable

base = 'Win32GUI' if sys.platform == 'win32' else None

includefiles = ['ffmpeg/', 'img/', 'models/']
includes = ['yt_dlp.utils._deprecated']
excludes = ['Tkinter']
packages = ["os", "moviepy", "imageio", "numpy"]

setup(
    name='AutoComper',
    version='1.1',
    description='Automatic Comp Creation Tool',
    author='wz-bff',
    options={'build_exe': {'includes': includes, 'excludes': excludes,
                           'packages': packages, 'include_files': includefiles}},
    executables=[Executable('autocomper.py',
                            base=base,
                            icon="app.ico")]
)
