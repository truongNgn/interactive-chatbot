import os
import urllib.request

def download_file(url, filename):
    print(f"Downloading {url} to {filename}...")
    if os.path.exists(filename):
        print(f"{filename} already exists. Skipping.")
        return
    urllib.request.urlretrieve(url, filename)
    print(f"Downloaded {filename} successfully.")

if __name__ == "__main__":
    # Download Kokoro ONNX model weights and voices mapping
    download_file("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx", "kokoro-v0_19.onnx")
    download_file("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin", "voices.bin")
    print("All model files downloaded successfully!")
