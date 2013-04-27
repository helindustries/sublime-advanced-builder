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
A build phase to run arbitrary commands
"""
from common import BuildPhase

class RunCommandPhase(BuildPhase):
    """
    A build phase to run arbitrary commands
    """

    def init(self, _settings, **kwargs):
        """
        Initialize the build phase, providing basic data.

        @param **kwargs The configuration to initialize the phase
        """
        super(RunCommandPhase, self).init(_settings, **kwargs)
        self._command = kwargs.get("command")

        if(self._command is None):
            self._invalidate("Mandatory setting 'command' missing")
        if(isinstance(self._command, dict)) and (not self._command.has("cmd")):
            self._invalidate("Malformed setting 'command'")
        if(isinstance(self._command, list)) and (len(self._command) < 1):
            self._invalidate("Malformed setting 'command'")

    def should_run(self):
        """
        This is called when building to determine whether or not the build phase
        should actually run for the current target. This is not queued, if build_all
        was set to true.

        @param target The target file, currently selected.
        @param current_config The currently active configuration.
        @return Whether or not the build should be executed.
        """
        path = self.path_selector
        if(path is not None):
            path = self.settings.expand_placeholders(self.path_selector)
            if(not path.endswith("/")):
                path += "/"

        return self.check_configuration() and self.check_task() \
                and (path is None or self.settings.active_file().startswith(path))

    def get_task(self):
        """
        Get the task data to perform for this build phase.

        @param commands A dictionary of predefined commands
        @returns A dictionary of settings to execute the command.
        """
        if(isinstance(self._command, list)):
            return self._get_list_command()
        elif(isinstance(self._command, dict)):
            return self._get_dict_command()

    def _expand_command(self, command_list):
        for i in range(len(command_list)):
            command_list[i] = self.settings.expand_placeholders(command_list[i])
        return command_list

    def _get_list_command(self):
        command_list = self._expand_command(self._command)

        # the first element may reference a predefined command.
        command = self.settings.command(command_list[0])
        if(command is None):
            # not a predefined command, build the required structure.
            command = {
                "cmd": command_list
            }
        else:
            # got a predefined command, add the remaining argument list
            command = command.copy()
            command["cmd"] = list(command["cmd"]) + command_list[1:]

        return command

    def _get_dict_command(self):
        self._command["cmd"] = self._expand_command(self._command["cmd"])

        command = self.settings.command(self._command["cmd"][0])
        if(command is None):
            # Not a predefined command, take it as is.
            # Don't fall back to defaults for additional flexibility
            return self._command

        # a predefined command, replace necessary structures.
        command = command.copy()
        command_list = list(command["cmd"]) + self._command["cmd"][1:]
        command.update(self._command)
        command["cmd"] = command_list

        return command

    def __repr__(self):
        return "Command phase: '%s' command: '%s' to: '%s' configs: '%s' valid: '%s'" % (self.name, self._command, self.configurations, self._is_valid)

