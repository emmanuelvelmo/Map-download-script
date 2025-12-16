from cx_Freeze import setup, Executable

setup(name="Map downloader", executables=[Executable("Map downloader script.py")], options={"build_exe": {"excludes": ["tkinter"]}})
