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
A build phase to run stylecop with on all files in a
certain directory.
"""
import re
import os
import os.path
from xml.dom.minidom import parse
import sublime

if int(sublime.version()) < 3000:
    from common import BuildPhase
else:
    from ..common import BuildPhase
def printcons(*msg):
    print(" ".join(str(x) for x in msg))

class StyleCopPhase(BuildPhase):
    """
    Phase to run stylecopcmd on files in a directory
    """

    def init(self, _settings, **kwargs):
        """
        Initialize the build phase, providing basic data.

        @param **kwargs The configuration to initialize the phase
        """
        super(StyleCopPhase, self).init(_settings, **kwargs)
        self._path = kwargs.get("path")
        self._settings_file = kwargs.get("settings")
        self._skip_filters = kwargs.get("skip_filters")
        self._result_limit = kwargs.get("limit_results")

        if(self._path is None) or (self._path == ""):
            self._invalidate("Mandatory setting 'path' missing")
        if(self._settings_file is None) or (self._settings_file == ""):
            self._invalidate("Mandatory setting 'settings' missing")
        if(self._skip_filters is None) or (not isinstance(self._skip_filters, list)):
            self._skip_filters = []
        if(self._result_limit is None) or (self._result_limit == ""):
            self._result_limit = 100

        if(not self._path.endswith("/")):
            self._path += "/"

        for i in range(len(self._skip_filters)):
            skip = self._skip_filters[i]
            if(not skip.startswith("^")):
                skip = "^.*" + skip

            if(not skip.endswith("$")):
                skip += ".*$"

            self._skip_filters[i] = re.compile(skip)

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
        if(path is None):
            path = self._path

        path = self.settings.expand_placeholders(path)
        path = path.replace(os.path.sep, "/")
        if(not path.endswith("/")):
            path += "/"

        return self.check_configuration() and self.check_task() \
                and (path is None or self.settings.active_file().startswith(path))

    def _find_files(self, path):
        """
        Find all files with the extension .cs in path.

        @param path The path to search
        @returns A list of files with the extension .cs
        """
        files = []
        for entry in os.listdir(path):
            if(entry == ".") or (entry == ".."):
                # parent or current directory, just skip
                continue

            full_path = os.path.join(path, entry).replace(os.path.sep, "/")
            if(self._match_skip_filter(full_path)):
                continue

            if(os.path.isdir(full_path)):
                # just append the content of the directory
                files += self._find_files(full_path)
            elif(entry.endswith(".cs")):
                # append the single file
                files.append(full_path)

        return files

    def _match_skip_filter(self, path):
        for skip in self._skip_filters:
            if(skip.match(path)):
                return True

        return False

    def get_task(self):
        """
        Get the task data to perform for this build phase.

        @param commands A dictionary of predefined commands
        @returns A dictionary of settings to execute the command.
        """
        path = self.settings.expand_placeholders(self._path)

        command = self.settings.command("stylecop")
        if(command is None):
            self._invalidate("StyleCop command not defined")
            return None

        command = command.copy()
        command_list = list(command["cmd"])
        command_list.append("-xml")
        command_list.append(os.path.join(path, "Violations.stylecop").replace(os.path.sep, "/"))
        command_list.append("-settings")
        command_list.append(self.settings.expand_placeholders(self._settings_file))
        command_list += self._find_files(path)
        command["cmd"] = command_list

        command["completion_callback"] = self.task_complete
        return command

    def task_complete(self, window_controller):
        """
        Called, when the task is completed.
        """
        path = self.settings.expand_placeholders(self._path)
        path = os.path.join(path, "Violations.stylecop").replace(os.path.sep, "/")
        has_violations = self.print_violations(path, window_controller)
        if(os.path.isfile(path)):
            os.remove(path);
        return has_violations;

    def print_violations(self, path, window_controller):
        """
        print violations from a StyleCop results file
        """
        # StyleCop doesn't end its data with a newline!
        # Because the error expressions need to match
        # our output, we need to wipe StyleCop's ass.
        window_controller.process_print("")

        if(not os.path.isfile(path)):
            # There is no results file, so no violations
            message = "No StyleCop violations found."
            window_controller.process_print(message)
            return False

        results = parse(path)
        count = 0

        files = results.getElementsByTagName("File")
        if(len(files) < 1):
            # There is a file, but it is empty!
            message = "No StyleCop violations found."
            window_controller.process_print(message)
            return False

        for f in files:
            if(self._result_limit != False) and (count > self._result_limit):
                message = "Too many StyleCop results, stopping..."
                window_controller.process_print(message)
                break

            violations = f.getElementsByTagName("Violation")
            file_name = f.getAttribute("Name")
            for violation in violations:
                line = violation.getAttribute("line")
                check_id = violation.getAttribute("CheckId")
                message = violation.getAttribute("message")

                # printcons(the warning)
                message = "%s(%s,0) warning:%s %s" % (file_name, line, check_id, message)
                window_controller.process_print(message)
                count += 1

        return (count > 0)

    def __repr__(self):
        return "StyleCop phase: '%s' path: '%s' configs: '%s' valid: '%s'" % (self.name, self._path, self.configurations, self._is_valid)

