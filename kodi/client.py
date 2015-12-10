#!/usr/bin/python
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

import xbmc
import xbmcaddon

from twisted.internet import reactor
from twisted.internet.defer import Deferred

from resources.lib.common import MediaType, EventName, StereoscopicMode, AspectRatio, Arg

from resources.lib.lib import DeviceClientFactory
from resources.lib.lib import QueuedLineSender

__addon__        = xbmcaddon.Addon()
__addonversion__ = __addon__.getAddonInfo('version')
__addonid__      = __addon__.getAddonInfo('id')
__addonname__    = __addon__.getAddonInfo('name')

class Device(QueuedLineSender):
    deviceId = 'kodi'
    
    def sendLine(self, line):
        d = Deferred()
        d.callback('UNSUPPORTED:' + line)
        return d

class Logger(object):
    @staticmethod
    def _log(txt, log_level=xbmc.LOGNOTICE, *args, **kwargs):
        if args or kwargs:
            txt = txt.format(*args, **kwargs)
        message = "{addonName}: {message}".format(addonName=__addonname__, message=txt.encode('ascii', 'ignore'))
        xbmc.log(msg=message, level=log_level)
    
    @staticmethod
    def info(txt, *args, **kwargs):
        Logger._log(txt, xbmc.LOGINFO, *args, **kwargs)
    
    @staticmethod
    def debug(txt, *args, **kwargs):
        Logger._log(txt, xbmc.LOGDEBUG, *args, **kwargs)
    
    @staticmethod
    def notice(txt, *args, **kwargs):
        Logger._log(txt, xbmc.LOGNOTICE, *args, **kwargs)
        
    @staticmethod
    def warning(txt, *args, **kwargs):
        Logger._log(txt, xbmc.LOGWARNING, *args, **kwargs)

def send_event(event, args=[]):
    call_args = [EventName(event)]
    call_args += args
    kodiDeviceClient.lineReceived(Arg.args_to_string(call_args))

class PlayerEventReceiver(xbmc.Player):
    curMediaType = None
    didStart3D = None
    
    def _sendEvent(self, event):

        args = []
       
        mediaType = self._getMediaType()
        
        if event == EventName.PLAYING:
            self.curMediaType = mediaType
        elif event == EventName.STOPPED:
            mediaType = self.curMediaType
            self.curMediaType = None

        args.append(MediaType(mediaType))
    
        if MediaType.isVideo(mediaType):
            stereoscopicMode = self._getStereoscopicMode()
            if event == EventName.PLAYING and stereoscopicMode.value == StereoscopicMode.HSBS:
                self.didStart3D = stereoscopicMode
            elif event == EventName.STOPPED and self.didStart3D:
                stereoscopicMode = self.didStart3D
                self.didStart3D = None
            
            args.append(stereoscopicMode) 
            args.append(self._getAspectRatio())
        
        send_event(event, args)

    def _getStereoscopicMode(self):
        return StereoscopicMode.fromKodi(xbmc.getInfoLabel('VideoPlayer.StereoscopicMode'))
        
    def _getAspectRatio(self):
        ratio = xbmc.getInfoLabel('VideoPlayer.VideoAspect') or AspectRatio.DEFAULT
        return AspectRatio(ratio)
        
    def _getMediaType(self):
        mediaType = MediaType.UNKNOWN

        if self.isPlayingAudio():
            mediaType = MediaType.MUSIC
        elif self.isPlayingVideo():
            
            # sometimes the player says it's playing a video but doesn't actually return the correct info for the video that
            # is playing. If we wait until VideoPlayer.Title is populated it seems to be mostly consistent. Sometimes the
            # aspect ratio is still wrong though.
            for i in range(10):
                if xbmc.getInfoLabel('VideoPlayer.Title') != '':
                    break

                Logger.notice("Player is not ready on attempt {}, waiting 10ms and trying again", i)
                xbmc.sleep(10)

            if xbmc.getCondVisibility('VideoPlayer.Content(movies)'):
                try:
                    filename = self.getPlayingFile()
                    if '-trailer' in filename:
                        mediaType = MediaType.TRAILER
                    elif filename.startswith('http://') or filename.startswith('https://'):
                        mediaType = MediaType.TRAILER
                    else:
                        mediaType = MediaType.MOVIE
                except:
                    Logger.notice("Exception trying to get the current filename")
                    pass
            elif xbmc.getCondVisibility('VideoPlayer.Content(episodes)') and xbmc.getInfoLabel('VideoPlayer.Season') != '' and xbmc.getInfoLabel('VideoPlayer.TVShowTitle') != '':
                mediaType = MediaType.EPISODE
            else:
                mediaType = MediaType.VIDEO
        else:
            Logger.notice('Unknown media type currently playing')
            
        return mediaType

    def onPlayBackStarted(self):
        self._sendEvent(EventName.PLAYING)

    def onPlayBackEnded(self):
        self.onPlayBackStopped()

    def onPlayBackStopped(self):
        self._sendEvent(EventName.STOPPED)

    def onPlayBackPaused(self):
        self._sendEvent(EventName.PAUSED)

    def onPlayBackResumed(self):
        self._sendEvent(EventName.RESUMED)

class MyMonitor(xbmc.Monitor):

    def onScreensaverActivated(self):
        send_event(EventName.SCREENSAVER_ACTIVATED)

    def onScreensaverDeactivated(self):
        send_event(EventName.SCREENSAVER_DEACTIVATED)

    def onDatabaseUpdated(self, db):
        send_event(EventName.DATABASE_UPDATED)

kodiDeviceClient = Device()
    
import threading
class TwistedThread(threading.Thread):
    def run(self):
        ip = __addon__.getSetting("device_server_ip")
        port = int(__addon__.getSetting("device_server_port"))

        reactor.connectTCP(ip, port, DeviceClientFactory(kodiDeviceClient))
        reactor.run(installSignalHandlers=0)

if __name__ == "__main__":
    Logger.notice('Script version {} started', __addonversion__)
    
    playerEventReceiver = PlayerEventReceiver()
    monitor = MyMonitor()

    thread = TwistedThread()
    thread.start()

    sent_idle = False

    # block here so the script stays active until XBMC shuts down
    while not xbmc.abortRequested:

        # watch for the idle time to cross the threshold and send the idle event when it does        
        if xbmc.getGlobalIdleTime() > 60 * int(__addon__.getSetting("idle_time")):
            if not sent_idle:
                send_event(EventName.IDLE)
                sent_idle = True
        else:
            if sent_idle:
                send_event(EventName.NOT_IDLE)
                sent_idle = False
        xbmc.sleep(1000)
    
    reactor.stop()
    Logger.notice('Script version {} stopped', __addonversion__)
