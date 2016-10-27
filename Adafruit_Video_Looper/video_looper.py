# Copyright 2015 Adafruit Industries.
# Author: Tony DiCola
# License: GNU GPLv2, see LICENSE.txt
import ConfigParser
import importlib
import os
import re
import sys
import signal
import time
import ujson as json

import gaugette.rotary_encoder
import gaugette.switch
import pygame

from model import Playlist
from collections import deque


# Basic video looper architecure:
#
# - VideoLooper class contains all the main logic for running the looper
#   program.
#
# - Almost all state is configured in a .ini config file which is required for
#   loading and using the VideoLooper class.
#
# - VideoLooper has loose coupling with file reader and video player classes
#   that are used to find movie files and play videos respectively.  The
#   configuration defines which file reader and video player module will be
#   loaded.
#
# - A file reader module needs to define at top level create_file_reader
#   function that takes as a parameter a ConfigParser config object.  The
#   function should return an instance of a file reader class.  See
#   usb_drive.py and directory.py for the two provided file readers and their
#   public interface.
#
# - Similarly a video player modules needs to define a top level create_player
#   function that takes in configuration.  See omxplayer.py and hello_video.py
#   for the two provided video players and their public interface.
#
# - Future file readers and video players can be provided and referenced in the
#   config to extend the video player use to read from different file sources
#   or use different video players.
class VideoLooper(object):

    def __init__(self, config_path):
        """Create an instance of the main video looper application class. Must
        pass path to a valid video looper ini configuration file.
        """
        # Load the configuration.
        self._config = ConfigParser.SafeConfigParser()
        if len(self._config.read(config_path)) == 0:
            raise RuntimeError('Failed to find configuration file at {0},' +
                               ' is the application properly installed?'
                               .format(config_path))
        self._console_output = self._config.getboolean('video_looper',
                                                       'console_output')
        # Load configured video player and file reader modules.
        self._player = self._load_player()
        self._reader = self._load_file_reader()
        # Load other configuration values.
        self._osd = self._config.getboolean('video_looper', 'osd')
        self._is_random = self._config.getboolean('video_looper', 'is_random')
        # Parse string of 3 comma separated values like "255, 255, 255" into
        # list of ints for colors.
        self._bgcolor = map(int, self._config.get('video_looper', 'bgcolor')
                                             .translate(None, ',')
                                             .split())
        self._fgcolor = map(int, self._config.get('video_looper', 'fgcolor')
                                             .translate(None, ',')
                                             .split())
        self._config_path = self._config.get('video_looper',
                                             'config_json_path')
        if os.path.exists(self._config_path) and not \
                os.path.isdir(self._config_path):
            try:
                with open(self._config_path, 'r') as config_file:
                    self._config_obj = json.load(config_file)
            except Exception as e:
                print('loading config obj:', e)
                self._config_obj = None
            else:
                encoder_gpio = self._config_obj['rotary']['gpio']
                self._rotary = gaugette.rotary_encoder\
                    .RotaryEncoder(encoder_gpio['pinA'],
                                   encoder_gpio['pinB'])
                self._switch = gaugette.switch.Switch(
                    self._config_obj['altButton']['gpio']['pin'])

        # Load sound volume file name value
        self._sound_vol_file = self._config.get('omxplayer', 'sound_vol_file')
        # default value to 0 millibels (omxplayer)
        self._sound_vol = 0
        # Initialize pygame and display a blank screen.
        pygame.display.init()
        pygame.font.init()
        pygame.mouse.set_visible(False)
        size = (pygame.display.Info().current_w,
                pygame.display.Info().current_h)
        self._screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
        self._blank_screen()
        # Set other static internal state.
        self._extensions = self._player.supported_extensions()
        self._small_font = pygame.font.Font(None, 50)
        self._big_font = pygame.font.Font(None, 250)
        self._running = True

    def _print(self, message):
        """Print message to standard output if console output is enabled."""
        if self._console_output:
            print(message)

    def _load_player(self):
        """Load the configured video player and return an instance of it."""
        module = self._config.get('video_looper', 'video_player')
        return importlib.import_module('.' + module, 'Adafruit_Video_Looper') \
            .create_player(self._config)

    def _load_file_reader(self):
        """Load the configured file reader and return an instance of it."""
        module = self._config.get('video_looper', 'file_reader')
        return importlib.import_module('.' + module, 'Adafruit_Video_Looper') \
            .create_file_reader(self._config)

    def _is_number(iself, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def _updateEncoderPostion(self):
        boundaries = self._config_obj['rotary']['boundaries']
        rotaryPosition = self._getRotaryPosition()
        try:
            self._encoderPosition
        except:
            self._encoderPosition = 0
            # self._encoderPosition = sum(
            #         boundaries[:self._getRotaryPosition()+1])
        delta = self._rotary.get_delta()
        if delta != 0:
            print('Encoder update: ', delta)
        self._encoderPosition += delta
        if self._encoderPosition <= -boundaries[rotaryPosition]:
            self._encoderPosition += boundaries[rotaryPosition]
            if rotaryPosition > 0:
                self._setRotaryPosition(rotaryPosition - 1)
        elif self._encoderPosition >= boundaries[rotaryPosition]:
            self._encoderPosition -= boundaries[rotaryPosition]
            if rotaryPosition < 3:
                self._setRotaryPosition(rotaryPosition + 1)

    def _setRotaryPosition(self, value):
        self._config_obj['rotary']['position'] = value
        self._save_json_config()

    def _getRotaryPosition(self):
        return self._config_obj['rotary']['position']

    def _save_json_config(self):
        try:
            with open(self._config_path, 'w') as config_file:
                json.dump(self._config_obj, config_file)
        except Exception as e:
            print('_save_json_config:', e)

    def _build_playlist(self):
        """Search all the file reader paths for movie files with the provided
        extensions.
        """
        # Get list of paths to search from the file reader.
        paths = self._reader.search_paths()
        if self._config_obj is not None:
            print('_build_playlist:', 'self._config_obj is not None')
            self._current_playlist = deque([])
            self._std_playlists = []
            self._alt_playlists = []

            try:
                playlists_path = self._config_obj['playlists']['standard']
                print('_build_playlist:', 'standard playlists')
                for path in playlists_path:
                    with open(os.path.join(paths[0], path), 'r')\
                            as playlist_file:
                        self._std_playlists.append(json.load(playlist_file))

                playlists_path = self._config_obj['playlists']['alternative']
                print('_build_playlist:', 'alternative playlists')
                for path in playlists_path:
                    with open(os.path.join(paths[0], path), 'r')\
                            as playlist_file:
                        self._alt_playlists.append(json.load(playlist_file))
                print('_build_playlist:', 'current playlist')
                self._current_playlist.extend(
                    (self._std_playlists if self._switch.get_state() == 0
                     else self._alt_playlists)[self._getRotaryPosition()])
            except Exception as e:
                print('_build_playlist load standard or alt', e)

            print('_build_playlist:', 'returning current playlist',
                  self._current_playlist)
            return self._current_playlist

    def _blank_screen(self):
        """Render a blank screen filled with the background color."""
        self._screen.fill(self._bgcolor)
        pygame.display.update()

    def _render_text(self, message, font=None):
        """Draw the provided message and return as pygame surface of it rendered
        with the configured foreground and background color.
        """
        # Default to small font if not provided.
        if font is None:
            font = self._small_font
        return font.render(message, True, self._fgcolor, self._bgcolor)

    def _animate_countdown(self, playlist, seconds=10):
        """Print text with the number of loaded movies and a quick countdown
        message if the on screen display is enabled.
        """
        # Print message to console with number of movies in playlist.
        message = 'Found {0} movie{1}.'\
                  .format(playlist.length(),
                          's' if playlist.length() >= 2 else '')
        self._print(message)
        # Do nothing else if the OSD is turned off.
        if not self._osd:
            return
        # Draw message with number of movies loaded and animate countdown.
        # First render text that doesn't change and get static dimensions.
        label1 = self._render_text(message + ' Starting playback in:')
        l1w, l1h = label1.get_size()
        sw, sh = self._screen.get_size()
        for i in range(seconds, 0, -1):
            # Each iteration of the countdown rendering changing text.
            label2 = self._render_text(str(i), self._big_font)
            l2w, l2h = label2.get_size()
            # Clear screen and draw text with line1 above line2 and all
            # centered horizontally and vertically.
            self._screen.fill(self._bgcolor)
            self._screen.blit(label1,
                              (sw / 2 - l1w / 2, sh / 2 - l2h / 2 - l1h))
            self._screen.blit(label2, (sw / 2 - l2w / 2, sh / 2 - l2h / 2))
            pygame.display.update()
            # Pause for a second between each frame.
            time.sleep(1)

    def _idle_message(self):
        """Print idle message from file reader."""
        # Print message to console.
        message = self._reader.idle_message()
        self._print(message)
        # Do nothing else if the OSD is turned off.
        if not self._osd:
            return
        # Display idle message in center of screen.
        label = self._render_text(message)
        lw, lh = label.get_size()
        sw, sh = self._screen.get_size()
        self._screen.fill(self._bgcolor)
        self._screen.blit(label, (sw / 2 - lw / 2, sh / 2 - lh / 2))
        pygame.display.update()

    def _prepare_to_run_playlist(self, playlist):
        """Display messages when a new playlist is loaded."""
        # If there are movies to play show a countdown first (if OSD enabled),
        # or if no movies are available show the idle message.
        if playlist.length() > 0:
            self._animate_countdown(playlist)
            self._blank_screen()
        else:
            self._idle_message()

    def _addTransitionToState(self, state):
        dirpath = self._reader.search_paths()[0]
        if state == 1:
            print('Adding transition from std to alt')
            self._current_playlist.extend(
                os.path.join(dirpath, self._config_obj
                             ['transitions']['stdToAlt']
                             [self._getRotaryPosition()]))
        else:
            print('Adding transition from alt to std')
            self._current_playlist.extend(
                os.path.join(dirpath, self._config_obj
                             ['transitions']['altToStd']
                             [self._getRotaryPosition()]))

    def run(self):
        """Main program loop.  Will never return!"""
        # Get playlist of movies to play from file reader.
        playlist = self._build_playlist()
        if playlist is None:
            self.signal_quit(None, None)
            return
        dirpath = self._reader.search_paths()[0]
        #######################################
        # self._prepare_to_run_playlist(playlist)
        #######################################
        # Main loop to play videos in the playlist and listen for file changes.
        swith_state = self._switch.get_state()
        while self._running:
            new_state = self._switch.get_state()
            if swith_state != new_state:
                print('Switch update: ', new_state)
                swith_state = new_state

            old_position = self._getRotaryPosition()
            self._updateEncoderPostion()
            new_position = self._getRotaryPosition()
            if old_position != new_position:
                pass

            # Load and play a new movie if nothing is playing.
            if not self._player.is_playing():
                if len(playlist) <= 1:
                    self._current_playlist.extend(self._std_playlists
                                                  [self._getRotaryPosition()])
                movie = playlist.popleft()
                if movie is not None:
                    # Start playing the first available movie.
                    self._print('Playing movie: {0}'.format(movie))
                    self._player.play(os.path.join(dirpath, movie),
                                      loop=False,  # playlist.length() == 1
                                      vol=self._sound_vol)

            # Give the CPU some time to do other tasks.
            time.sleep(0.002)

    def signal_quit(self, signal, frame):
        """Shut down the program, meant to by called by signal handler."""
        self._running = False
        if self._player is not None:
            self._player.stop()
        pygame.quit()


# Main entry point.
if __name__ == '__main__':
    print('Starting Adafruit Video Looper.')
    # Default config path to /boot.
    config_path = '/boot/video_looper.ini'
    # Override config path if provided as parameter.
    if len(sys.argv) == 2:
        config_path = sys.argv[1]
    # Create video looper.
    videolooper = VideoLooper(config_path)
    # Configure signal handlers to quit on TERM or INT signal.
    signal.signal(signal.SIGTERM, videolooper.signal_quit)
    signal.signal(signal.SIGINT, videolooper.signal_quit)
    # Run the main loop.
    videolooper.run()
