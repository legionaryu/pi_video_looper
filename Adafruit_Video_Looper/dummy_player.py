# Copyright 2015 Adafruit Industries.
# Author: Tony DiCola
# License: GNU GPLv2, see LICENSE.txt
import os
import time
import threading
from functools import wraps


def delay(delay=0.):
    """
    Decorator delaying the execution of a function for a while.
    """
    def wrap(f):
        @wraps(f)
        def delayed(*args, **kwargs):
            timer = threading.Timer(delay, f, args=args, kwargs=kwargs)
            timer.start()
        return delayed
    return wrap


class DummyVideoPlayer(object):

    def __init__(self, config):
        """Create an instance of a video player that runs hello_video.bin in the
        background.
        """
        self._is_playing = False

    def supported_extensions(self):
        """Return list of supported file extensions."""
        return '*.*'

    def play(self, movie, loop=False, **kwargs):
        self._is_playing = True
        self.__stop_playing()

    def is_playing(self):
        """Return true if the video player is running, false otherwise."""
        return self._is_playing

    def stop(self, block_timeout_sec=None):
        """Stop the video player.  block_timeout_sec is how many seconds to
        block waiting for the player to stop before moving on.
        """
        self._is_playing = False

    @delay(3)
    def __stop_playing():
        self._is_playing = False


def create_player(config):
    """Create new video player based on hello_video."""
    return DummyVideoPlayer(config)
