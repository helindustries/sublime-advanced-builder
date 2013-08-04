# License:
#
# Copyright (c) 2013, Paul Schulze
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
"""
The copy files build phase.
"""
import os.path
import glob
import sublime

if int(sublime.version()) < 3000:
    from common import BuildPhase
else:
    from ..common import BuildPhase
def printcons(*msg):
    print(" ".join(str(x) for x in msg))

class CopyFilesPhase(BuildPhase):
    """
    A Copy files build phase.
    """

    def init(self, _settings, **kwargs):
        """
        Initialize the build phase, providing basic data.

        @param **kwargs The configuration to initialize the phase
        """
        super(CopyFilesPhase, self).init(_settings, **kwargs)

        self._from_paths = kwargs.get("sources")
        self._to_path = kwargs.get("destination")

        # Verify the configuration
        if(self._from_paths is None) or (not isinstance(self._from_paths, list)) or (len(self._from_paths) <= 0):
            self._invalidate("Mandatory setting 'sources' missing")
        if(self._to_path is None) or (self._to_path == ""):
            self._invalidate("Mandatory setting 'destination' missing")


    def should_run(self):
        """
        This is called when building to determine whether or not the build phase
        should actually run for the current target. This is not queued, if build_all
        was set to true.

        @param target The target file, currently selected.
        @param current_config The currently active configuration.
        @return Whether or not the files should be copied.
        """
        path = self.path_selector
        if(path is not None):
            path = os.path.dirname(self.settings.expand_placeholders(path))
            if(not path.endswith("/")):
                path += "/"

        return self.check_configuration() and self.check_task() \
                and (path is None or self.settings.active_file().startswith(path))

    def _expand_files(self, file_list):
        path_list = []
        for path in file_list:
            # Make the necessary expansions for Sublime Text, user directories
            # environment variables and placeholders, in that order
            path = self.settings.expand_placeholders(path)
            path = os.path.expanduser(path)
            path = os.path.expandvars(path)
            path_list += glob.glob(path)
        return path_list

    def get_task(self):
        """
        Get the task data to perform for this build phase.

        @param commands A dictionary of predefined commands
        @returns A dictionary of settings to execute the command.
        """
        command = self.settings.command("copy")
        if(command is None):
            self._invalidate("Copy command not defined")
            return None

        command = command.copy()

        command_list = list(command["cmd"]) + self._expand_files(self._from_paths)
        command_list.append(self.settings.expand_placeholders(self._to_path))
        command["cmd"] = command_list

        return command

    def __repr__(self):
        return "CopyFiles phase: '%s' type: '%s' from: '%s' to: '%s' configs: '%s' valid: '%s'" % (self.name, self._type, self._from_paths, self._to_path, self.configurations, self._is_valid)
