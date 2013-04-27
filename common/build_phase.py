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
The basis for all build phases
"""
import sublime

class BuildPhase(object):
    """
    Base class for build phases, recording custom names and the configurations,
    the phase applies to.
    """

    def init(self, _settings, **kwargs):
        """
        Initialize the build phase, providing basic data.

        @param name The name of the build phase.
        """
        self.settings = _settings
        self.name = kwargs.get("name")
        self.path_selector = kwargs.get("path_selector")
        self.stop_on_error = kwargs.get("stop_on_error")
        self.configurations = kwargs.get("configurations")
        self._is_valid = True
        self._type = kwargs.get("type")

        # Verify the base state
        if(self.name is None):
            # Default to an empty string.
            self.name = ""
        if(self.stop_on_error is None):
            # Default to true, because otherwise, subsequent tasks may fails.
            self.stop_on_error = True
        if(self._type is None) or (self._type == ""):
            # No type, go nuts!
            self._invalidate("Invalid build phase")
        if(self.configurations == []):
            # This phase won't do anything, warn.
            self._invalidate("No configuration enabled")
        if(self.tasks is None):
            # This phase does not specify a task, default to Build-only.
            self.tasks = ["Build"]
        if(self.tasks == []):
            # This phase won't do anything, warn.
            self._invalidate("No tasks enabled")

    def is_valid(self):
        """
        Check, whether the configuration of this phase is valid. If not, it
        will neither get a call to should_run() nor to execute().
        """
        return self._is_valid

    def _invalidate(self, message):
        """
        Invalidate this configuration with a message to the user.

        @param message The message to print.
        """
        if(self.name != ""):
            message += ": " + self.name

        if(self._type == ""):
            message += ", no type defined!"
        else:
            " of type " + self._type

        self._is_valid = False
        sublime.error_message(message + " skipping it!")

    def check_configuration(self):
        return (self.configurations is None or self.settings.active_configuration() in self.configurations)

    def check_task(self):
        return (self.tasks is None or self.settings.active_task() in self.tasks)

    def should_run(self, target, current_config):
        """
        This is called when building to determine whether or not the build phase
        should actually run for the current target. This is not queued, if build_all
        was set to true.

        @param target The target file, currently selected.
        @param current_config The currently active configuration.
        @returns Whether or not the build should be executed.
        """
        raise Exception("'Abstract' method Phase.should_run() not implemented!")

    def get_task(self):
        """
        Get the task data to perform for this build phase. This should have the following format:

        {
            "working_dir": <the working directory for the task>,
            "cmd": <the command to execute as a list of executable and parameters>,
            "file_regex": <the regular expression, identifying files>,
            "line_regex": <the regular expression, identifying lines>,
        }

        @param commands A dictionary of predefined commands
        @returns A dictionary of settings to execute the command. This has to have the following format:
        """
        raise Exception("'Abstract' method Phase.execute() not implemented!")

    def __repr__(self):
        return "%s: '%s' type: '%s' configs: '%s' valid: '%s'" % (self.__class__.__name__, self.name, self.type, self._configurations, self._is_valid)

    def __str__(self):
        label = self.name
        if(label == ""):
            label = self.__class__.__name__
        else:
            label += " (" + self.__class__.__name__ + ")"

        return label
