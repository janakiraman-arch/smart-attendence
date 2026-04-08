import wave
import math
import struct

def generate_beep(filename='assets/alarm.wav', duration=1.0, frequency=1000.0, sample_rate=44100):
    """Generates a beep sound and saves it as a .wav file."""
    print(f"Generating {filename}...")
    
    # Calculate number of frames
    n_frames = int(duration * sample_rate)
    
    # Open the file
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1)  # Mono
        obj.setsampwidth(2)  # 2 bytes per sample (16-bit)
        obj.setframerate(sample_rate)
        
        # Generate the frames
        for i in range(n_frames):
            # value = sin(2 * pi * frequency * t)
            t = i / sample_rate
            value = int(32767.0 * math.sin(2.0 * math.pi * frequency * t))
            data = struct.pack('<h', value)
            obj.writeframesraw(data)
            
    print(f"File {filename} created successfully.")

if __name__ == "__main__":
    generate_beep()
