#!/usr/bin/env python
# vim:set ts=8 sw=4 sts=4 et:

# Copyright (c) 2007-2013 Serban Giuroiu
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# ------------------------------------------------------------------------------

import getopt
import os
import pdb
import queue
import re
import subprocess
import sys
import threading
import time

# ------------------------------------------------------------------------------

PATH_PREFIX             = ''   # /usr/bin, /usr/local/bin, etc.

AFCONVERT               = os.path.join(PATH_PREFIX, 'afconvert')
ATOMICPARSELEY          = os.path.join(PATH_PREFIX, 'AtomicParsley')
FAAD                    = os.path.join(PATH_PREFIX, 'faad')
FLAC                    = os.path.join(PATH_PREFIX, 'flac')
LAME                    = os.path.join(PATH_PREFIX, 'lame')
MADPLAY                 = os.path.join(PATH_PREFIX, 'madplay')
METAFLAC                = os.path.join(PATH_PREFIX, 'metaflac')
OGGDEC                  = os.path.join(PATH_PREFIX, 'oggdec')
OGGENC                  = os.path.join(PATH_PREFIX, 'oggenc')
VORBISCOMMENT           = os.path.join(PATH_PREFIX, 'vorbiscomment')

TMPDIR                  = '/tmp'
NAME                    = 'piggy'

ALAC_FILE_EXTENSIONS    = ['m4a']
AIFF_FILE_EXTENSIONS    = ['aif', 'aiff']
FLAC_FILE_EXTENSIONS    = ['flac']
MP3_FILE_EXTENSIONS     = ['mp3']
MP4_FILE_EXTENSIONS     = ['mp4', 'm4a']
VORBIS_FILE_EXTENSIONS  = ['ogg']
WAVE_FILE_EXTENSIONS    = ['wav']

EXIT_SUCCESS            = 0
EXIT_FAILURE            = 1
EXIT_CMDFAILURE         = 2

# TTY Colors
NOCOLOR                 = '\033[0m'
RED                     = '\033[01;31m'
GREEN                   = '\033[01;32m'
YELLOW                  = '\033[01;33m'
BLUE                    = '\033[01;34m'
MAGENTA                 = '\033[01;35m'
CYAN                    = '\033[01;36m'
WHITE                   = '\033[01;37m'
#WHITE                  = '\033[37;40m'

encoderSettings         = []            # See below

# ------------------------------------------------------------------------------

def msg(s):
    print(GREEN + '*', s, NOCOLOR)

def err(s):
    print(RED + '!', s, NOCOLOR)

def dbg(s):
    if __debug__:
        print(YELLOW + '%', s, NOCOLOR)

def sep():
    try:
        columns = subprocess.getoutput('stty size').split()[1]
    except IndexError:
        columns = 80

    print(WHITE, end='')
    for i in range(int(columns)):
        print('-', end='')
    print(NOCOLOR)

class Timer(object):
    def start(self):
        self.startTime = int(time.time())

    def stop(self):
        self.endTime = int(time.time())

    def timeDelta(self):
        return self.endTime - self.startTime

    def stringDelta(self):
        total = self.timeDelta()

        days    = total     // 86400
        remain  = total     %  86400
        hours   = remain    //  3600
        remain  = remain    %   3600
        minutes = remain    //    60
        seconds = remain    %     60

        return str(days) + 'd ' + str(hours) + 'h ' + str(minutes) + 'm ' + str(seconds) + 's'

def escape(str):
#   TODO: This is probably not adequate nor secure
#
#   escape strings:    replace " with \"

    r = re.compile('"')
    s = r.sub('\\"', str)

    return s

def numCores():
#   From http://www.boduch.ca/2009/06/python-cpus.html
#   TODO: make this more reliable
    if 'SC_NPROCESSORS_ONLN' in os.sysconf_names:
        # Linux
        num = os.sysconf('SC_NPROCESSORS_ONLN')
    else:
        # Mac OS X
        num = int(subprocess.getoutput('sysctl -n hw.ncpu'))

    if num < 1:
        err('Could not determine the number of cores available')
        return 1
    else:
        return num

def runProcess(s):
    if __debug__:
        print(CYAN + '>', s, NOCOLOR)

#   TODO: return subprocess.call(s) should be adequate
    p = subprocess.Popen(s, shell=True)
    return p.wait()

def deleteFile(s):
    dbg('Deleting ' + s)
    os.remove(s)

# ------------------------------------------------------------------------------

class AudioFile(object):
    def __init__(self, path):
        # AudioFile objects should not exist unless their respective files exist
        # on disk!
        assert os.path.isfile(path)
        assert os.access(path, os.R_OK)

        self.path = path                                    # Full path to the file on disk
        self.dir, self.name = os.path.split(path)           # Absolute directory and filename
        self.name_noext = os.path.splitext(self.name)[0]    # Filename without the period and the extension
        self.decodedAudioFile = None                        # A decoded version of this file; typically a WaveAudioFile
        self.tags = {}                                      # { artist, album, title, track, year, comment }

        self.loadTags()

    def generateTempFileName(self, s):
        # This is not meant to be secure. It'd be nice to use the tempfile
        # module, but we just need a *name*, not a file handle.
        # TODO: On Mac OS X, we can use `getconf DARWIN_USER_TEMP_DIR`
        name = os.path.join(TMPDIR, NAME + '_' + str(time.time()) + '_' + s)
        return name

    def removeTemporaryFiles(self):
        if self.decodedAudioFile:
            deleteFile(self.decodedAudioFile.path)
            self.decodedAudioFile = None

    def decode(self):
        pass

    def loadTags(self):
        pass

    def setTags(self, artist, album, title, track, year, comment):
        self.tags['artist']     = artist
        self.tags['album']      = album
        self.tags['title']      = title
        self.tags['track']      = track
        self.tags['year']       = year
        self.tags['comment']    = comment

class PCMAudioFile(AudioFile):
    def decode(self):
        return self

class WaveAudioFile(PCMAudioFile):
    pass

class AIFFAudioFile(PCMAudioFile):
    pass

class CompressedAudioFile(AudioFile):
    pass

class ALACAudioFile(CompressedAudioFile):
    def decode(self):
        if self.decodedAudioFile:
            return self.decodedAudioFile

        outputPath = self.generateTempFileName(self.name + '.wav')

        # TODO: Hmm... we're assuming 16 bits per sample. Is this a good idea?
        exitCode = runProcess(AFCONVERT + ' -f WAVE -d LEI16 "' + escape(self.path) + '" "' + escape(outputPath) + '"')
        if exitCode == 0:
            decodedAudioFile = WaveAudioFile(outputPath)
            decodedAudioFile.tags = self.tags
            self.decodedAudioFile = decodedAudioFile
            return decodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

    def loadTags(self):
        tags = subprocess.getoutput(ATOMICPARSELEY + ' "' + escape(self.path) + '" -t')

        ar = re.compile('Atom "©ART" contains: (.+)', re.IGNORECASE)
        al = re.compile('Atom "©alb" contains: (.+)', re.IGNORECASE)
        ti = re.compile('Atom "©nam" contains: (.+)', re.IGNORECASE)
        tr = re.compile('Atom "trkn" contains: (.+)', re.IGNORECASE)
        yr = re.compile('Atom "©day" contains: (\d+)', re.IGNORECASE)
#        cm = re.compile('Atom "©cmt" contains: (.+)', re.IGNORECASE)

        for line in tags.splitlines():
            m = ar.match(line)
            if m:
                self.tags['artist'] = m.group(1)

            m = al.match(line)
            if m:
                self.tags['album'] = m.group(1)

            m = ti.match(line)
            if m:
                self.tags['title'] = m.group(1)

            m = tr.match(line)
            if m:
                self.tags['track'] = m.group(1)

            m = yr.match(line)
            if m:
                self.tags['year'] = m.group(1)

#            m = cm.match(line)
#            if m:
#                self.tags['comment'] = m.group(1)

class XiphAudioFile(CompressedAudioFile):
    def xiphLoadTags(self, tool):
        tags = subprocess.getoutput(tool)

        ar = re.compile('ARTIST=(.+)', re.IGNORECASE)
        al = re.compile('ALBUM=(.+)', re.IGNORECASE)
        ti = re.compile('TITLE=(.+)', re.IGNORECASE)
        tr = re.compile('TRACKNUMBER=(.*)', re.IGNORECASE)
        yr = re.compile('DATE=(.*)', re.IGNORECASE)
        cm = re.compile('COMMENT=(.*)', re.IGNORECASE)

        for line in tags.splitlines():
            m = ar.match(line)
            if m:
                self.tags['artist'] = m.group(1)

            m = al.match(line)
            if m:
                self.tags['album'] = m.group(1)

            m = ti.match(line)
            if m:
                self.tags['title'] = m.group(1)

            m = tr.match(line)
            if m:
                self.tags['track'] = m.group(1)

            m = yr.match(line)
            if m:
                self.tags['year'] = m.group(1)

            m = cm.match(line)
            if m:
                self.tags['comment'] = m.group(1)

class FLACAudioFile(XiphAudioFile):
    def decode(self):
        if self.decodedAudioFile:
            return self.decodedAudioFile

        outputPath = self.generateTempFileName(self.name + '.wav')

        exitCode = runProcess(FLAC + ' --silent --decode -o "' + escape(outputPath) + '" "' + escape(self.path) + '"')
        if exitCode == 0:
            decodedAudioFile = WaveAudioFile(outputPath)
            decodedAudioFile.tags = self.tags
            self.decodedAudioFile = decodedAudioFile
            return decodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

    def loadTags(self):
        self.xiphLoadTags(METAFLAC + ' --export-tags-to=- "' + escape(self.path) + '"')

class VorbisAudioFile(XiphAudioFile):
    def decode(self):
        if self.decodedAudioFile:
            return self.decodedAudioFile

        outputPath = self.generateTempFileName(self.name + '.wav')

        exitCode = runProcess(OGGDEC + ' --quiet -o "' + escape(outputPath) + '" "' + escape(self.path) + '"')
        if exitCode == 0:
            decodedAudioFile = WaveAudioFile(outputPath)
            decodedAudioFile.tags = self.tags
            self.decodedAudioFile = decodedAudioFile
            return decodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

    def loadTags(self):
        self.xiphLoadTags(VORBISCOMMENT + ' --list "' + escape(self.path) + '"')

class MP3AudioFile(CompressedAudioFile):
    def decode(self):
        if self.decodedAudioFile:
            return self.decodedAudioFile

        outputPath = self.generateTempFileName(self.name + '.wav')

        exitCode = runProcess(MADPLAY + ' --quiet -o "' + escape(outputPath) + '" "' + escape(self.path) + '"')
        if exitCode == 0:
            decodedAudioFile = WaveAudioFile(outputPath)
            decodedAudioFile.tags = self.tags
            self.decodedAudioFile = decodedAudioFile
            return decodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

    def loadTags(self):
        tags = subprocess.getoutput(MADPLAY + ' --show-tags-only "' + escape(self.path) + '"')

        ar = re.compile('\s*artist: (.+)', re.IGNORECASE)
        al = re.compile('\s*album: (.+)', re.IGNORECASE)
        ti = re.compile('\s*title: (.+)', re.IGNORECASE)
        tr = re.compile('\s*track: (.*)', re.IGNORECASE)
        yr = re.compile('\s*year: (.*)', re.IGNORECASE)
#        cm = re.compile('comment: (.*)', re.IGNORECASE)

        for line in tags.splitlines():
            m = ar.match(line)
            if m:
                self.tags['artist'] = m.group(1)

            m = al.match(line)
            if m:
                self.tags['album'] = m.group(1)

            m = ti.match(line)
            if m:
                self.tags['title'] = m.group(1)

            m = tr.match(line)
            if m:
                self.tags['track'] = m.group(1)

            m = yr.match(line)
            if m:
                self.tags['year'] = m.group(1)

#            m = cm.match(line)
#            if m:
#                self.tags['comment'] = m.group(1)

class MP4AudioFile(CompressedAudioFile):
    def decode(self):
        if self.decodedAudioFile:
            return self.decodedAudioFile

        outputPath = self.generateTempFileName(self.name + '.wav')

        exitCode = runProcess(FAAD + ' --quiet -o "' + escape(outputPath) + '" "' + escape(self.path) + '"')
        if exitCode == 0:
            decodedAudioFile = WaveAudioFile(outputPath)
            decodedAudioFile.tags = self.tags
            self.decodedAudioFile = decodedAudioFile
            return decodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

    def loadTags(self):
        tags = subprocess.getoutput(FAAD + ' --info "' + escape(self.path) + '"')

        ar = re.compile('artist: (.+)', re.IGNORECASE)
        al = re.compile('album: (.+)', re.IGNORECASE)
        ti = re.compile('title: (.+)', re.IGNORECASE)
        tr = re.compile('track: (.*)', re.IGNORECASE)
        yr = re.compile('date: (.*)', re.IGNORECASE)
#        cm = re.compile('COMMENT=(.*)', re.IGNORECASE)

        for line in tags.splitlines():
            m = ar.match(line)
            if m:
                self.tags['artist'] = m.group(1)

            m = al.match(line)
            if m:
                self.tags['album'] = m.group(1)

            m = ti.match(line)
            if m:
                self.tags['title'] = m.group(1)

            m = tr.match(line)
            if m:
                self.tags['track'] = m.group(1)

            m = yr.match(line)
            if m:
                self.tags['year'] = m.group(1)

#            m = cm.match(line)
#            if m:
#                self.tags['comment'] = m.group(1)

def makeAudioFile(path):
    # TODO: Need a more intelligent way other than file extension to tell a
    #       filetype
    if os.path.isfile(path) and os.access(path, os.R_OK):
        name = os.path.basename(path)

        try:
            ext = os.path.splitext(name)[1].split('.')[1].lower()
        except IndexError:
            return None

        # .m4a files can be either ALAC or MP4. Since ALAC comes first in this
        # list, it masks MP4.
        if ext in AIFF_FILE_EXTENSIONS:
            return AIFFAudioFile(path)
        elif ext in ALAC_FILE_EXTENSIONS:
            return ALACAudioFile(path)
        elif ext in FLAC_FILE_EXTENSIONS:
            return FLACAudioFile(path)
        elif ext in MP3_FILE_EXTENSIONS:
            return MP3AudioFile(path)
        elif ext in MP4_FILE_EXTENSIONS:
            return MP4AudioFile(path)
        elif ext in VORBIS_FILE_EXTENSIONS:
            return VorbisAudioFile(path)
        elif ext in WAVE_FILE_EXTENSIONS:
            return WaveAudioFile(path)

    return None

# ------------------------------------------------------------------------------

class AudioEncoder(object):
    def __init__(self, opts):
        self.opts = opts

    def encode(self, audioFile, outputPath):
        '''Decode the audioFile if necessary. Then, encode the
        audioFile. The encoder adds the appropriate extension to
        outputPath and writes the encoded file to that path.

        Return the encoded AudioFile if successful, None otherwise
        '''
        pass

class ALACAudioEncoder(AudioEncoder):
    def encode(self, audioFile, outputPath):
        outputPath += '.m4a'

        pcmAudioFile = audioFile.decode()

        if pcmAudioFile == None:
            return None

        cmd = AFCONVERT + ' -d alac ' + self.opts + ' "' + escape(pcmAudioFile.path) + \
                '" "' + escape(outputPath) + '"'
        exitCode = runProcess(cmd)

        if exitCode != 0:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

        cmd = ATOMICPARSELEY + ' "' + escape(outputPath) + '" --overWrite'

        if 'artist' in audioFile.tags:
            cmd += ' --artist "' + escape(audioFile.tags['artist']) + '"'
        if 'album' in audioFile.tags:
            cmd += ' --album "' + escape(audioFile.tags['album']) + '"'
        if 'title' in audioFile.tags:
            cmd += ' --title "' + escape(audioFile.tags['title']) + '"'
        if 'track' in audioFile.tags:
            cmd += ' --tracknum "' + escape(audioFile.tags['track']) + '"'
        if 'year' in audioFile.tags:
            cmd += ' --year "' + escape(audioFile.tags['year']) + '"'
        if 'comment' in audioFile.tags:
            cmd += ' --comment "' + escape(audioFile.tags['comment']) + '"'

        exitCode = runProcess(cmd)

        if exitCode == 0:
            encodedAudioFile = ALACAudioFile(outputPath)
            encodedAudioFile.tags = audioFile.tags
            return encodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

class FLACAudioEncoder(AudioEncoder):
    def encode(self, audioFile, outputPath):
        outputPath += '.flac'

        pcmAudioFile = audioFile.decode()

        if pcmAudioFile == None:
            return None

        cmd = FLAC + ' --silent ' + self.opts

        if 'artist' in audioFile.tags:
            cmd += ' -T ARTIST="' + escape(audioFile.tags['artist']) + '"'
        if 'album' in audioFile.tags:
            cmd += ' -T ALBUM="' + escape(audioFile.tags['album']) + '"'
        if 'title' in audioFile.tags:
            cmd += ' -T TITLE="' + escape(audioFile.tags['title']) + '"'
        if 'track' in audioFile.tags:
            cmd += ' -T TRACKNUMBER="' + escape(audioFile.tags['track']) + '"'
        if 'year' in audioFile.tags:
            cmd += ' -T DATE="' + escape(audioFile.tags['year']) + '"'
        if 'comment' in audioFile.tags:
            cmd += ' -T COMMENT="' + escape(audioFile.tags['comment']) + '"'

        cmd += ' -o "' + escape(outputPath) + \
                '" "' + escape(pcmAudioFile.path) + '"'
        exitCode = runProcess(cmd)

        if exitCode == 0:
            encodedAudioFile = FLACAudioFile(outputPath)
            encodedAudioFile.tags = audioFile.tags
            return encodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

class OggencAudioEncoder(AudioEncoder):
    def encode(self, audioFile, outputPath):
        outputPath += '.ogg'

        pcmAudioFile = audioFile.decode()

        if pcmAudioFile == None:
            return None

        cmd = OGGENC + ' --quiet ' + self.opts

        if 'artist' in audioFile.tags:
            cmd += ' -a "' + escape(audioFile.tags['artist']) + '"'
        if 'album' in audioFile.tags:
            cmd += ' -l "' + escape(audioFile.tags['album']) + '"'
        if 'title' in audioFile.tags:
            cmd += ' -t "' + escape(audioFile.tags['title']) + '"'
        if 'track' in audioFile.tags:
            cmd += ' -N "' + escape(audioFile.tags['track']) + '"'
        if 'year' in audioFile.tags:
            cmd += ' -d "' + escape(audioFile.tags['year']) + '"'
        if 'comment' in audioFile.tags:
            cmd += ' -c "COMMENT=' + escape(audioFile.tags['comment']) + '"'

        cmd += ' -o "' + escape(outputPath) + \
                '" "' + escape(pcmAudioFile.path) + '"'
        exitCode = runProcess(cmd)

        if exitCode == 0:
            encodedAudioFile = VorbisAudioFile(outputPath)
            encodedAudioFile.tags = audioFile.tags
            return encodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

class LAMEAudioEncoder(AudioEncoder):
    def encode(self, audioFile, outputPath):
        outputPath += '.mp3'

        pcmAudioFile = audioFile.decode()

        if pcmAudioFile == None:
            return None

        cmd = LAME + ' --silent ' + self.opts

        if 'artist' in audioFile.tags:
            cmd += ' --ta "' + escape(audioFile.tags['artist']) + '"'
        if 'album' in audioFile.tags:
            cmd += ' --tl "' + escape(audioFile.tags['album']) + '"'
        if 'title' in audioFile.tags:
            cmd += ' --tt "' + escape(audioFile.tags['title']) + '"'
        if 'track' in audioFile.tags:
            cmd += ' --tn "' + escape(audioFile.tags['track']) + '"'
        if 'year' in audioFile.tags:
            cmd += ' --ty "' + escape(audioFile.tags['year']) + '"'
        if 'comment' in audioFile.tags:
            cmd += ' --tc "' + escape(audioFile.tags['comment']) + '"'

        cmd += ' "' + escape(pcmAudioFile.path) + \
                '" "' + escape(outputPath) + '"'
        exitCode = runProcess(cmd)

        if exitCode == 0:
            encodedAudioFile = MP3AudioFile(outputPath)
            encodedAudioFile.tags = audioFile.tags
            return encodedAudioFile
        else:
            try:
                deleteFile(outputPath)
            except OSError:
                pass
            return None

# ------------------------------------------------------------------------------

class FileList(object):
    '''Store the absolute paths to all of the files under one root directory'''

    def __init__(self, rootPath, absoluteFilePaths):
        self.rootPath           = rootPath
        self.absoluteFilePaths  = absoluteFilePaths

class EncoderSetting(object):
    def __init__(self, name, folder, extension, encoder):
        self.name       = name
        self.folder     = folder
        self.extension  = extension
        self.encoder    = encoder

def findEncoderSetting(name):
    for s in encoderSettings:
        if s.name == name:
            return s

    return None

class EncoderAndOutputPath(object):
    def __init__(self, setting, outputPath):
        self.setting    = setting
        self.outputPath = outputPath
        self.encoder    = setting.encoder

class QueueEntry(object):
    def __init__(self, number, inputAudioFile):
        self.number                = number
        self.inputAudioFile        = inputAudioFile
        self.encoderAndOutputPaths = []

    def addEncoderAndOutputPath(self, setting, outputPath):
        self.encoderAndOutputPaths.append(EncoderAndOutputPath(setting,
                                                            outputPath))

# ------------------------------------------------------------------------------

def parseCommandLine():
    # return (settings, input directories, output directory)

    # Accept the following command line arguments:
    #   -s  Encoder Setting  (at least one)
    #   -i  Input Directory  (at least one)
    #       Output Directory (exactly one)

    settings            = []
    inputDirectories    = []
    outputDirectory     = ''

    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:i:')
    except getopt.GetoptError as e:
        err(e)
        sys.exit(EXIT_CMDFAILURE)

    if len(args) != 1:
        err('You must specify exactly one output directory')
        sys.exit(EXIT_CMDFAILURE)
    else:
        outputDirectory = os.path.normpath(args[0])

    for opt, arg in opts:
        if opt == '-s':
            setting = findEncoderSetting(arg)

            if setting:
                if settings.count(setting) > 0:
                    err('Encoder setting "' + arg + '" was specified more than once')
                    sys.exit(EXIT_CMDFAILURE)
                else:
                    settings.append(setting)
            else:
                err('Encoder setting "' + arg + '" does not exist')
                sys.exit(EXIT_CMDFAILURE)
        elif opt == '-i':
            dir = os.path.normpath(arg)
            if os.path.isdir(dir):
                for d in inputDirectories:
                    if os.path.basename(d) == os.path.basename(dir):
                        err('WARNING: Duplicate basenames in input directories: ' + os.path.basename(dir))
                inputDirectories.append(dir)
            else:
                err('Not a directory: ' + dir)
                sys.exit(EXIT_CMDFAILURE)

    if len(settings) < 1:
        err('You must specify at least one encoder setting')
        sys.exit(EXIT_CMDFAILURE)

    if len(inputDirectories) < 1:
        err('You must specify at least one input folder')
        sys.exit(EXIT_CMDFAILURE)

    return (settings, inputDirectories, outputDirectory)

def recursiveFileList(root):
    '''Return a FileList of all the files in a directory'''

    absoluteFilePaths = []

    # Clean up the root path (and remove the trailing slash)
    root = os.path.normpath(root)

    for dirpath, dirnames, filenames in os.walk(root):
        # Add every non-hidden file in the directory to the list
        for file in filenames:
            if file.startswith('.'):
                dbg('Ignoring file ' + os.path.join(dirpath, file))
            else:
                absoluteFilePaths.append(os.path.join(dirpath, file))

    absoluteFilePaths.sort()

    return FileList(root, absoluteFilePaths)

def populateQueue(inputQueue, settings, inputFileLists, outputDirectory):
    counter = 1

    for fileList in inputFileLists:
        for filePath in fileList.absoluteFilePaths:
            audioFile = makeAudioFile(filePath)
            if audioFile:
                queueEntry = QueueEntry(counter, audioFile)
                counter += 1

                # Add a trailing slash to the rootPath
                rootStr = os.path.join(fileList.rootPath, '')
                relativeFilePath = filePath.split(rootStr, 1)[1]
                relativeFilePathWithoutExtension = os.path.splitext(
                                                    relativeFilePath)[0]

                rootName = os.path.basename(fileList.rootPath)

                for setting in settings:
                    outputPath = os.path.join(outputDirectory,
                                    setting.folder, rootName,
                                    relativeFilePathWithoutExtension)
                    queueEntry.addEncoderAndOutputPath(setting, outputPath)

                inputQueue.put(queueEntry)
            else:
#               TODO: It might be a good idea to keep track of these and dump
#               them when transcoding has finished
                err('Could not make an AudioFile out of ' + filePath)

    if inputQueue.qsize() < 1:
        err('No audio files found')
        sys.exit(EXIT_SUCCESS)

def dumpShitList(shitList):
    size = shitList.qsize()

    if size > 0:
        err('The following ' + str(size) + ' files could not be transcoded:')

        while True:
            try:
                entry = shitList.get(block=False)
                err('  ' + entry.inputAudioFile.path)
            except queue.Empty:
                break

    return size

# ------------------------------------------------------------------------------

def worker(threadNum, inputQueue, queueSize, shitList):
    while True:
        try:
            entry = inputQueue.get(block=False)
        except queue.Empty:
            dbg('Thread ' + str(threadNum) + ' finished')
            return

        prefix = '[{:> 6} / {:>6}]: '.format(entry.number, queueSize)
        msg(prefix + 'Transcoding ' + entry.inputAudioFile.name)

        decodedAudioFile = entry.inputAudioFile.decode()

        if decodedAudioFile is None:
            err(prefix + 'Decode failed')
            shitList.put(entry)
            continue

        for pair in entry.encoderAndOutputPaths:
            folderPath = os.path.dirname(pair.outputPath)
            try:
                dbg(prefix + 'Making directories for ' + folderPath)
                os.makedirs(folderPath, exist_ok=True)
            except OSError as e:
                err(prefix + 'Could not make directories for "' + folderPath + '": ' + e.strerror)
                shitList.put(entry)
                break

            dbg(prefix + 'Encoding with ' + pair.setting.name)
            encodedAudioFile = pair.encoder.encode(decodedAudioFile,
                                                    pair.outputPath)
            if encodedAudioFile is None:
                err(prefix + 'Encoding with ' + pair.setting.name + ' failed')
                shitList.put(entry)
                break

        entry.inputAudioFile.removeTemporaryFiles()
        dbg(prefix + 'Finished')

def spawnThreads(inputQueue, queueSize, shitList):
    workers = []

    # Spawn and run all the worker threads
    for i in range(1, numCores() + 1):
        dbg('Spawning thread ' + str(i))
        thread = threading.Thread(target=worker, args=[i, inputQueue, queueSize, shitList])
        workers.append(thread)
        thread.start()

    # The workers will finish once the queue is empty. Everything is
    # done when all workers have finished.
    for w in workers:
        w.join()

def main():
    inputFileLists  = []                # A list of FileList objects
    inputQueue      = queue.Queue()
    shitList        = queue.Queue()

    settings, inputDirectories, outputDirectory = parseCommandLine()

    for s in settings:
        msg('Encoding with ' + s.name)

    for d in inputDirectories:
        msg('Searching ' + d)

    msg('Outputting to ' + outputDirectory)

    for d in inputDirectories:
        inputFileLists.append(recursiveFileList(d))

    populateQueue(inputQueue, settings, inputFileLists, outputDirectory)
    queueSize = inputQueue.qsize()

    timer = Timer()

    sep()

    timer.start()
    spawnThreads(inputQueue, queueSize, shitList)
    timer.stop()

    sep()

    shitListSize = dumpShitList(shitList)
    msg('Encoded ' + str(queueSize - shitListSize) + ' files in ' + timer.stringDelta())

# ------------------------------------------------------------------------------

encoderSettings = [
#                   NAME            FOLDER         EXTENSION    ENCODER
    EncoderSetting('alac',          'alac',         'm4a',      ALACAudioEncoder('')),
    EncoderSetting('flac',          'flac',         'flac',     FLACAudioEncoder('--best --verify')),
    EncoderSetting('oggenc-q5',     'vorbis-q5',    'ogg',      OggencAudioEncoder('-q 5')),
    EncoderSetting('lame-vbr2',     'mp3-vbr2',     'mp3',      LAMEAudioEncoder('-m j -h --vbr-new -V 2 --id3v2-only --noreplaygain')),
    EncoderSetting('lame-cbr192',   'mp3-cbr192',   'mp3',      LAMEAudioEncoder('-m j -h -b 192 --id3v2-only --noreplaygain')),
    EncoderSetting('lame-cbr256',   'mp3-cbr256',   'mp3',      LAMEAudioEncoder('-m j -h -b 256 --id3v2-only --noreplaygain')),
    EncoderSetting('lame-standard', 'mp3-standard', 'mp3',      LAMEAudioEncoder('--preset standard --id3v2-only --noreplaygain')),
    EncoderSetting('lame-extreme',  'mp3-extreme',  'mp3',      LAMEAudioEncoder('--preset extreme --id3v2-only --noreplaygain')),
    EncoderSetting('lame-insane',   'mp3-insane',   'mp3',      LAMEAudioEncoder('--preset insane --id3v2-only --noreplaygain')),
]

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
