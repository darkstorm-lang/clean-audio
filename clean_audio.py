#!/bin/python
#pylint: disable=too-few-public-methods, missing-docstring, C0413
#-----------------------------------------------------------------------------
# Darkstorm Library
# Copyright (C) 2017 Martin Slater
# Created : Tuesday, 31 October 2017 12:41:28 PM
#-----------------------------------------------------------------------------
"""
Module for cleaning audio tracks intended for anki.
See README.md for more details and clean_audio.py --help for usage instructions.
"""

#-------------------------------------------------------------------------------------------------
# # Imports
#-------------------------------------------------------------------------------------------------
from __future__ import absolute_import, print_function
import argparse
import glob
import os
import os.path as path
import sys
import platform

# on windows update the environment so pydub can find the executables for loading
# mp3 audio files.
if platform.system() == 'Windows':
    BIN_DIR = path.join(path.dirname(path.realpath(__file__)), 'bin', 'win', 'bin')
    os.environ['PATH'] = BIN_DIR + ";" + os.environ['PATH']

from pydub import AudioSegment
from pydub.effects import normalize
from pydub.utils import db_to_float, ratio_to_db

#-------------------------------------------------------------------------------------------------
# Class
#-------------------------------------------------------------------------------------------------
class CleanAudio(object):
    """ CleanAudio """

    def __init__(self, args):
        """ Constructor """
        self._input_files = []
        self._output_dir = args.output

        if not path.exists(self._output_dir):
            os.makedirs(self._output_dir)

        self._silence_threshold = -50
        self._silence_slice = 10 # ms
        self._dump_rms = args.dump_rms

        if '*' in args.input:
            self._input_files = glob.glob(args.input)
        elif path.exists(args.input):
            if path.isfile(args.input):
                self._input_files.append(args.input)
            elif path.isdir(args.input):
                p = path.abspath(args.input)
                for name in os.listdir(p):
                    self._input_files.append(path.join(p, name))
            else:
                sys.stderr.write('Invalid input - %s\n' % args.input)
                exit(1)

    TRIM_START = 0
    TRIM_END = 1

    def trim_silence(self, seg, trim):
        seg_len = len(seg)

        # you can't have a silent portion of a sound that is longer than the sound
        if seg_len < self._silence_slice:
            return []

        # convert silence threshold to a float value (so we can compare it to rms)
        silence_thresh = db_to_float(self._silence_threshold) * seg.max_possible_amplitude

        max_noise = 100
        noise_start = None
        # find silence and add start and end indicies to the to_cut list
        indices = range(seg_len / self._silence_slice)
        if trim == CleanAudio.TRIM_END:
            indices = reversed(indices)

        for idx in indices:
            start_ms = idx * self._silence_slice
            end_ms = start_ms + self._silence_slice
            seg_slice = seg[start_ms:end_ms]
            if seg_slice.rms > silence_thresh:
                if noise_start is None:
                    # start checking for burst of noise
                    noise_start = start_ms
                elif abs(start_ms - noise_start) > max_noise:
                    # length of noise exceeds threshold for burst so we are done
                    if trim == CleanAudio.TRIM_START:
                        return seg[noise_start:seg_len]
                    else:
                        return seg[0:noise_start+self._silence_slice]
            else:
                # back to silence, if we had noise it will be within burst threshold so
                # reset and keep looking for truly noisy section
                if noise_start is not None:
                    noise_start = None

        if noise_start is not None:
            if trim == CleanAudio.TRIM_START:
                return seg[noise_start:]
            else:
                return seg[0:noise_start+self._silence_slice]

        return seg

    def dump_rms(self, seg):
        seg_len = len(seg)
        for idx in range(seg_len - self._silence_slice):
            seg_slice = seg[idx:idx + self._silence_slice]
            print('%s' % (ratio_to_db(float(seg_slice.rms) /seg.max_possible_amplitude)))

    def clean_audio(self, seg):
        seg = self.trim_silence(seg, CleanAudio.TRIM_START)
        seg = self.trim_silence(seg, CleanAudio.TRIM_END)
        seg = normalize(seg, headroom=0.3)
        return seg

    def run(self):
        for ifile in self._input_files:
            ext = path.splitext(ifile)[1][1:]
            audio = None
            if ext == 'mp3':
                audio = AudioSegment.from_mp3(ifile)
            elif ext == 'wav':
                audio = AudioSegment.from_wav(ifile)
            else:
                sys.stderr.write('Unrecognised extension - %s\n', ext)

            if self._dump_rms:
                self.dump_rms(audio)
            else:
                audio = self.clean_audio(audio)
                dst = path.abspath(path.join(self._output_dir, path.basename(ifile)))
                audio.export(dst, format=ext)


#-----------------------------------------------------------------------------
# Main
#-----------------------------------------------------------------------------

def main():
    """ Main script entry point """
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input',
                        help='Input source, may be single file, directory or a glob',
                        dest='input')
    parser.add_argument('-o', '--output',
                        help='Output directory',
                        dest='output')
    parser.add_argument('-d', '--dump-rms',
                        help='Dump csv list of rms values for the input file to stdout',
                        dest='dump_rms', action='store_true')
    args = parser.parse_args()
    CleanAudio(args).run()

if __name__ == "__main__":
    main()
