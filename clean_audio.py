#!/bin/python
#pylint: disable=too-few-public-methods, missing-docstring, C0413
# -----------------------------------------------------------------------------
# Darkstorm Library
# Copyright (C) 2017 Martin Slater
# Created : Tuesday, 31 October 2017 12:41:28 PM
# -----------------------------------------------------------------------------
"""
Module for cleaning audio tracks intended for anki.
See README.md for more details and clean_audio.py --help for usage instructions.
"""

# -------------------------------------------------------------------------------------------------
# # Imports
# -------------------------------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import argparse
import glob
import hashlib
import json
import math
import os
import os.path as path
import platform
import shutil
import sqlite3
import sys
import tempfile

from pydub import AudioSegment
from pydub.effects import normalize
from pydub.utils import db_to_float, ratio_to_db

# on windows update the environment so pydub can find the executables for loading
# mp3 audio files.
if platform.system() == 'Windows':
    BIN_DIR = path.join(path.dirname(path.realpath(__file__)),
                        'bin', 'win')  # , 'usr', 'bin')
    print(BIN_DIR)
    os.environ['PATH'] = BIN_DIR + ";" + os.environ['PATH']
# elif platform.system() == 'Darwin':
#     BIN_DIR = path.join(path.dirname(path.realpath(__file__)), 'bin', 'osx')
#     print(os.environ)
#     os.environ['PATH'] = BIN_DIR + ";" + os.environ['PATH']


def is_audio_extension(ext):
    return ext in ['.wav', '.mp3', '.3gp']


def get_file_sha1(filename):
    sha1 = hashlib.sha1()
    with open(filename, 'rb') as infile:
        data = infile.read()
        sha1.update(data)
    return sha1.hexdigest()


class AudioFiles(object):
    def __init__(self, directory):
        self._dir = directory
        self._info = self.load_info_file()
        if self._info is None:
            self._info = {'files': {}}
        self.audio_files = self.get_new_audio_files()

    def info_file_path(self):
        return path.join(self._dir, 'clean_audio.json')

    def load_info_file(self):
        info_path = self.info_file_path()
        if path.exists(info_path):
            with open(info_path, 'rt') as info:
                info = json.load(info)
                #tmp = {}
                # for key, val in info['files'].iteritems():
                #    if '3gp' not in key:
                #        tmp[key] = val
                #info['files'] = tmp
                return info

        return None

    def save_info_file(self):
        self.update_hashes()
        with open(self.info_file_path(), "w") as info_file:
            json.dump(self._info, info_file)

    def update_hashes(self):
        for file in self.audio_files:
            self._info['files'][path.basename(
                file)]['sha1'] = get_file_sha1(file)

    def get_new_audio_files(self):
        audio_files = []
        for root, _, files in os.walk(self._dir):
            for filename in files:
                name = path.join(root, filename)
                if is_audio_extension(path.splitext(name)[1]):
                    update = True
                    basename = path.basename(filename)
                    new_sha1 = get_file_sha1(name)
                    if basename in self._info['files']:
                        old_sha1 = self._info['files'][basename]['sha1']
                        if old_sha1 == new_sha1:
                            update = False
                        else:
                            self._info['files'][basename]['sha1'] = new_sha1
                    else:
                        self._info['files'][basename] = {'sha1': new_sha1}

                    if update:
                        audio_files.append(name)

        return audio_files


class AnkiProfile(object):
    def __init__(self, root, name):
        self._root = root
        self.name = name
        self._dir = path.join(root, name, 'collection.media')
        self._audio_files = AudioFiles(self._dir)

    def directory(self):
        return self._dir

    def save_info_file(self):
        self._audio_files.save_info_file()

    def get_new_audio_files(self):
        return self._audio_files.audio_files


class Anki(object):
    """ Access to anki data """

    def __init__(self):
        self._anki_dir = None
        self._profiles = []

        if platform.system() == 'Windows':
            self._anki_dir = path.join(os.getenv('APPDATA'), 'Anki2')
        elif platform.system() == 'Darwin':
            self._anki_dir = path.join(
                os.getenv('HOME'), 'Library', 'Application Support', 'Anki2')
        else:
            print('Unknown platform "{0}" aborting'.format(platform.system()))

        connect = sqlite3.connect(path.join(self._anki_dir, 'prefs21.db'))
        for row in connect.execute('SELECT * FROM profiles'):
            name = row[0]
            if name != '_global':
                self._profiles.append(AnkiProfile(self._anki_dir, name))

    def profiles(self):
        return self._profiles

# -------------------------------------------------------------------------------------------------
# Class
# -------------------------------------------------------------------------------------------------


class CleanAudio(object):
    """ CleanAudio """
    TRIM_START = 0
    TRIM_END = 1

    def __init__(self, args):
        """ Constructor """
        self._input_files = []
        self._output_dir = args.output

        if not path.exists(self._output_dir):
            os.makedirs(self._output_dir)

        self._burst_threshold = -20
        self._silence_threshold = -50
        self._silence_slice = 10  # ms
        self._dump_rms = args.dump_rms

        if '*' in args.input:
            allfiles = glob.glob(args.input)
            for ifile in allfiles:
                if path.isfile(ifile) and CleanAudio.is_audio_file(ifile):
                    self._input_files.append(ifile)
        elif isinstance(args.input, list):
            self._input_files = args.input
        elif path.exists(args.input):
            if path.isfile(args.input):
                self._input_files.append(args.input)
            elif path.isdir(args.input):
                p = path.abspath(args.input)
                for name in os.listdir(p):
                    name = path.join(p, name)
                    if path.isfile(name) and CleanAudio.is_audio_file(name):
                        self._input_files.append(name)
            else:
                sys.stderr.write('Invalid input - %s\n' % args.input)
                exit(1)

    @staticmethod
    def is_audio_file(filename):
        ext = path.splitext(filename)[1]
        return ext in ('.mp3', '.wav', '.3gp')

    def trim_silence(self, seg, trim):
        seg_len = len(seg)

        # you can't have a silent portion of a sound that is longer than the sound
        if seg_len < self._silence_slice:
            return []

        # convert silence threshold to a float value (so we can compare it to rms)
        silence_thresh = db_to_float(
            self._silence_threshold) * seg.max_possible_amplitude
        burst_thresh = db_to_float(
            self._burst_threshold) * seg.max_possible_amplitude

        leading_ms = 250
        max_noise = 100
        end_extra_ms = 200
        noise_start = None
        noise_peak = None

        # find silence and add start and end indicies to the to_cut list
        indices = range(int(seg_len / self._silence_slice))
        if trim == CleanAudio.TRIM_END:
            indices = reversed(indices)

        for idx in indices:
            start_ms = idx * self._silence_slice
            end_ms = start_ms + self._silence_slice
            seg_slice = seg[start_ms:end_ms]
            if seg_slice.rms > silence_thresh:
                if noise_peak is None:
                    noise_peak = seg_slice.rms
                if seg_slice.rms > noise_peak:
                    noise_peak = seg_slice.rms

                if noise_start is None:
                    # start checking for burst of noise
                    noise_start = start_ms
                elif abs(start_ms - noise_start) > max_noise:
                    # length of noise exceeds threshold for burst so we are done
                    if trim == CleanAudio.TRIM_START:
                        return seg[noise_start:seg_len]
                    end = noise_start + self._silence_slice + end_extra_ms
                    if end > seg_len:
                        end = seg_len
                    return seg[0:end]
            else:
                # back to silence, if the noise exceeded the burst threshold
                # then reset and keep going, otherwise we have hit a small
                # pause in the audio
                if noise_start is not None and noise_peak > burst_thresh:
                    noise_start = None

        if noise_start is not None:
            if trim == CleanAudio.TRIM_START:
                start = math.max(noise_start - leading_ms, 0)
                return seg[start:]
            end = noise_start + self._silence_slice + end_extra_ms
            if end > seg_len:
                end = seg_len
            return seg[0:end]

        return seg

    def dump_rms(self, seg):
        seg_len = len(seg)
        for idx in range(seg_len - self._silence_slice):
            seg_slice = seg[idx:idx + self._silence_slice]
            print('%s' % (ratio_to_db(float(seg_slice.rms) / seg.max_possible_amplitude)))

    def clean_audio(self, seg):
        seg = normalize(seg, headroom=0.3)
        seg = self.trim_silence(seg, CleanAudio.TRIM_START)
        seg = self.trim_silence(seg, CleanAudio.TRIM_END)
        return seg

    def run(self):
        for ifile in self._input_files:
            bitrate = None
            ext = path.splitext(ifile)[1][1:]
            audio = None
            if ext == 'mp3':
                audio = AudioSegment.from_mp3(ifile)
            elif ext == 'wav':
                audio = AudioSegment.from_wav(ifile)
            elif ext == '3gp':
                print('Cannot convert .3pg. Ignoring ' + ifile)
                continue
                # this loads the file correctly but will fail on export below on os x at least
                #audio = AudioSegment.from_file(ifile, '3gp')
                #bitrate = 8000
            else:
                sys.stderr.write('Unrecognised extension - %s\n' % ext)
                continue

            # reduce to mono, no need for stereo
            audio = audio.set_channels(1)

            if bitrate != None:
                audio = audio.set_frame_rate(bitrate)

            sys.stdout.write('Processing %s...' % path.basename(ifile))
            if self._dump_rms:
                self.dump_rms(audio)
            else:
                audio = self.clean_audio(audio)
                dst = path.abspath(
                    path.join(self._output_dir, path.basename(ifile)))
                audio.export(dst, format=ext)
            sys.stdout.write('done\n')
        num = len(self._input_files)
        print('Processed %s %s' % (num, 'file' if num == 1 else 'files'))

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main():
    """ Main script entry point """
    parser = argparse.ArgumentParser(
        description='Module for cleaning audio tracks intended for Anki')
    parser.add_argument('-a', '--anki',
                        help='Update Anki media directory',
                        dest='anki', action='store_true')
    parser.add_argument('-s', '--simulate',
                        help='Show what would be processed but don\'t acutally do anything',
                        dest='simulate', action='store_true')
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

    if args.anki:
        anki = Anki()
        profile = None
        if len(anki.profiles()) > 1:
            cur = 1
            for profile in anki.profiles():
                print(str(cur) + ": " + profile.name)
                cur += 1
            sys.stdout.write('Select profile: ')
            choice = None
            while choice is None:
                try:
                    choice = int(raw_input('> '))
                    choice -= 1
                    if choice < 0 or choice >= len(anki.profiles()):
                        choice = None
                except ValueError:
                    choice = None

                if choice is None:
                    print("Invalid option")
            profile = anki.profiles()[choice]
        else:
            profile = anki.profiles()[0]

        files_to_update = profile.get_new_audio_files()

        if files_to_update:
            if args.simulate:
                for filename in files_to_update:
                    print(filename)
            else:
                tempdir = tempfile.mkdtemp()
                args.input = files_to_update
                args.output = tempdir
                CleanAudio(args).run()
                # copy all files back to the media directory
                for root, _, files in os.walk(tempdir):
                    for filename in files:
                        src = path.join(root, filename)
                        dst = path.join(profile.directory(), filename)
                        os.unlink(dst)
                        shutil.copyfile(src, dst)
                        os.unlink(src)
                profile.save_info_file()
        else:
            print('Nothing needs to be done.')

    elif (args.input is None or args.output is None):
        parser.error('Input and output directories must be specified.')
    else:
        CleanAudio(args).run()


if __name__ == "__main__":
    main()
