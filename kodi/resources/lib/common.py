# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

class Arg(object):
    arg_sep = ';'
    event_sep = '='
    
    def __init__(self, value):
        self.value = value
    
    def _format_arg(self):
        return '{arg}{sep}{value}'.format(arg=self.arg_name, sep=Arg.event_sep, value=self.value)

    @staticmethod
    def args_to_string(args):
        return Arg.arg_sep.join([x._format_arg() for x in args])

    @staticmethod
    def args_from_string(args):
        return dict([x.split(Arg.event_sep) for x in args.split(Arg.arg_sep)])

    @classmethod
    def get(cls, args):
        if type(args) == str:
            args = Arg.args_from_string(args)
        
        if cls.arg_name not in args:
            return ''
        else:
            return args[cls.arg_name]

class MediaType(Arg):
    arg_name = 'mediaType'
    
    MOVIE = "MOVIE"
    MUSIC = "MUSIC"
    EPISODE = "EPISODE"
    VIDEO = "VIDEO"
    TRAILER = "TRAILER"
    UNKNOWN = "UNKNOWN"
    
    @staticmethod
    def isVideo(mediaType):
        return mediaType in (MediaType.MOVIE, MediaType.EPISODE, MediaType.VIDEO, MediaType.TRAILER)

class StereoscopicMode(Arg):
    arg_name = 'stereoscopic'
    
    NONE = "2D"
    HSBS = "HSBS"
    UNKNOWN = "UNKNOWN"
    
    @staticmethod
    def fromKodi(kodiValue):
        if kodiValue == '':
            return StereoscopicMode(StereoscopicMode.NONE)
        elif kodiValue == 'left_right':
            return StereoscopicMode(StereoscopicMode.HSBS)
        else:
            return StereoscopicMode(StereoscopicMode.UNKNOWN)

class AspectRatio(Arg):
    arg_name = 'aspectRatio'
    
    DEFAULT = 'DEFAULT'
    # 1.33, 1.37, 1.66, 1.78, 1.85, 2.20, 2.35, 2.40, 2.55, 2.76

class EventName(Arg):
    arg_name = 'event'
    
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    STOPPED = "STOPPED"
    IDLE = "IDLE"
    NOT_IDLE = "NOT_IDLE"
    SCREENSAVER_ACTIVATED = "SCREENSAVER_ACTIVATED" 
    SCREENSAVER_DEACTIVATED = "SCREENSAVER_DEACTIVATED"
    DATABASE_UPDATED = "DATABASE_UPDATED"
