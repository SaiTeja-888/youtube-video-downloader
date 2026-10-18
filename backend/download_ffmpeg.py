import os
import urllib.request
import zipfile
import shutil

ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
ZIP_PATH = "ffmpeg.zip"
EXTRACT_DIR = "ffmpeg_temp"
DEST_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print(f"Downloading FFmpeg from {ZIP_URL}...")
    try:
        urllib.request.urlretrieve(ZIP_URL, ZIP_PATH)
        print("Download complete. Extracting...")
        
        # Create temp extraction folder
        if os.path.exists(EXTRACT_DIR):
            shutil.rmtree(EXTRACT_DIR)
        os.makedirs(EXTRACT_DIR)
        
        # Extract zip
        with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
            
        print("Locating ffmpeg binaries...")
        # Walk and find ffmpeg.exe & ffprobe.exe
        binaries_found = 0
        for root, dirs, files in os.walk(EXTRACT_DIR):
            for file in files:
                if file in ["ffmpeg.exe", "ffprobe.exe"]:
                    src = os.path.join(root, file)
                    dst = os.path.join(DEST_DIR, file)
                    shutil.move(src, dst)
                    print(f"Moved {file} to {dst}")
                    binaries_found += 1
                    
        if binaries_found >= 2:
            print("FFmpeg and FFprobe successfully installed locally!")
        else:
            print(f"Warning: Only found {binaries_found} binaries.")
            
    except Exception as e:
        print(f"Error installing FFmpeg: {e}")
    finally:
        # Cleanup
        if os.path.exists(ZIP_PATH):
            os.remove(ZIP_PATH)
        if os.path.exists(EXTRACT_DIR):
            shutil.rmtree(EXTRACT_DIR)

if __name__ == "__main__":
    main()
