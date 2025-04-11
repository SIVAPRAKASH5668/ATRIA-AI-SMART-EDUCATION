import whisper_timestamped as whisper
from whisper_timestamped import load_model, transcribe_timestamped
import re

import os
# Set FFmpeg path - adjust this to your actual FFmpeg installation path
os.environ["PATH"] += os.pathsep + r"C:ffmpeg\bin"

def generate_timed_captions(audio_filename, model_size="base"):
    try:
        WHISPER_MODEL = load_model(model_size)
        print(audio_filename)
        gen = transcribe_timestamped(WHISPER_MODEL, audio_filename, verbose=False, fp16=False)
        return getCaptionsWithTime(gen)
    except FileNotFoundError:
        print("ERROR: FFmpeg not found. Please install FFmpeg and make sure it's in your system PATH.")
        print("You can download FFmpeg from: https://ffmpeg.org/download.html")
        return [((0, 1), "Error: FFmpeg missing")]
    except Exception as e:
        print(f"ERROR generating captions: {e}")
        return [((0, 1), "Error generating captions")]

def splitWordsBySize(words, maxCaptionSize):
   
    halfCaptionSize = maxCaptionSize / 2
    captions = []
    while words:
        caption = words[0]
        words = words[1:]
        while words and len(caption + ' ' + words[0]) <= maxCaptionSize:
            caption += ' ' + words[0]
            words = words[1:]
            if len(caption) >= halfCaptionSize and words:
                break
        captions.append(caption)
    return captions

def getTimestampMapping(whisper_analysis):
   
    index = 0
    locationToTimestamp = {}
    for segment in whisper_analysis['segments']:
        for word in segment['words']:
            newIndex = index + len(word['text'])+1
            locationToTimestamp[(index, newIndex)] = word['end']
            index = newIndex
    return locationToTimestamp

def cleanWord(word):
   
    return re.sub(r'[^\w\s\-_"\'\']', '', word)

def interpolateTimeFromDict(word_position, d):
   
    for key, value in d.items():
        if key[0] <= word_position <= key[1]:
            return value
    return None

def getCaptionsWithTime(whisper_analysis, maxCaptionSize=15, considerPunctuation=False):
   
    wordLocationToTime = getTimestampMapping(whisper_analysis)
    position = 0
    start_time = 0
    CaptionsPairs = []
    text = whisper_analysis['text']
    
    if considerPunctuation:
        sentences = re.split(r'(?<=[.!?]) +', text)
        words = [word for sentence in sentences for word in splitWordsBySize(sentence.split(), maxCaptionSize)]
    else:
        words = text.split()
        words = [cleanWord(word) for word in splitWordsBySize(words, maxCaptionSize)]
    
    for word in words:
        position += len(word) + 1
        end_time = interpolateTimeFromDict(position, wordLocationToTime)
        if end_time and word:
            CaptionsPairs.append(((start_time, end_time), word))
            start_time = end_time

    return CaptionsPairs
