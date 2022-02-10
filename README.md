## Script to clean audio files for intended for use in anki

This will normalise the audio level and remove leading and trailing silence and noise bursts for either a given audio file or all of your anki media files. 


### Setup
To install first clone the repository using  ```git clone https://github.com/darkstorm-lang/clean-audio.git```

and then run `setup_env.bat` on windows or `setup_env.sh` on OS X or Linux.

### Anki

To normalise and clean anki media files just run

```python clean-audio.py -a```

This will process all files that have changed in your anki media collection since it was last run.

### Command line options

For up to date help type `python clean-audio.py -h`

```
usage: clean_audio.py [-h] [-a] [-s] [-i INPUT] [-o OUTPUT] [-d]

Module for cleaning audio tracks intended for Anki

optional arguments:
  -h, --help            show this help message and exit
  -a, --anki            Update Anki media directory
  -s, --simulate        Show what would be processed but don't actually do anything
  -i INPUT, --input INPUT
                        Input source, may be single file, directory or a glob
  -o OUTPUT, --output OUTPUT
                        Output directory
  -d, --dump-rms        Dump csv list of rms values for the input file to stdout
```
