import subprocess
import sys
import platform
import shutil
import time

class SetupLibrary:

    @staticmethod
    def install_choco():
        try:
            subprocess.check_call(["powershell", "-Command", r"Set-ExecutionPolicy Bypass -Scope Process -Force; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"])
        except subprocess.CalledProcessError:
            print("Failed to install Chocolatey.")

    @staticmethod
    def install_ffmpeg():
        system_platform = platform.system()

        if shutil.which("ffmpeg"):
            print("ffmpeg is already installed.")
            return

        if system_platform == "Linux":
            try:
                subprocess.check_call(["sudo", "apt-get", "install", "ffmpeg"])
            except subprocess.CalledProcessError:
                print("Failed to install ffmpeg on Linux.")
        elif system_platform == "Windows":
            try:
                SetupLibrary.install_choco()  # Install Chocolatey if not present
                subprocess.check_call(["choco", "install", "ffmpeg"])
            except subprocess.CalledProcessError:
                print("Failed to install ffmpeg on Windows.")

    @staticmethod
    def install_requirements():
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        except subprocess.CalledProcessError:
            print("Failed to install required packages.")
    # Install the required packages at the beginning of the script

    @staticmethod
    def setup():
        print("==== attempt installing required library ====")
        SetupLibrary.install_requirements()
        print("==== attempt installing required library - complete ====")
        time.sleep(3)
        print("==== install ffmpeg ====")
        SetupLibrary.install_ffmpeg()
        print("==== install ffmpeg - compelete ====")