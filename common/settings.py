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
A settings object for AdvancedBuilder
"""

import re
import os
import json
import os.path
import sublime
import time

class SettingsWriter(object):

    def __init__(self, window, path, data):
        self._window = window
        self._path = path
        self._data = data
        self._view = None
        self._last_view = None
        self._project_file_open = False
        self._done = False

    def save(self):
        # XXX: This is a very, very dirty hack because the API of
        #      sublime is very, very limited in this scope.
        for view in self._window.views():
            if(view.file_name() == self._path):
                self._project_file_open = True
                break

        # Open the settings file and start waiting
        self._last_view = self._window.active_view().file_name()
        self._view = self._window.open_file(self._path)
        print "Saving:", self._path
        self._do_save()


    def _do_save(self):
        if(self._view.is_loading()):
            print "View still not open, waiting"
            sublime.set_timeout(self._do_save, 100)
            return

        print "View opened, making changes"
        if(self._window.active_view().file_name() != self._path):
            # The last view has changed, update it.
            print "The view changed, updating"
            self._last_view = self._window.active_view().file_name()

        # The view has finished loading, present it again and start editing
        self._view = self._window.open_file(self._path)
        edit = self._view.begin_edit()

        # Replace the whole content of the file with the new settings
        all_region = sublime.Region(0, self._view.size())
        new_settings = json.dumps(self._data, indent = 4, separators = (',', ': '))
        self._view.replace(edit, all_region, new_settings)

        # Finish editing, save the file and close it
        self._view.end_edit(edit)
        self._window.run_command("save")
        if(self._project_file_open):
            # The settings file was open, don't close it
            self._window.open_file(self._last_view)
        else:
            # And away it goes
            self._window.run_command("close")
            pass

class AdvancedBuilderSettings(object):
    """
    Wrapper to expand a path, that contains place-holders.
    """

    SETTINGS_FILE = "AdvancedBuilder.sublime-settings"
    BUILD_FILE = "AdvancedBuilder.sublime-build"

    PROJECT_PATH_RECURSION_DEPTH = 2

    def __init__(self, window):
        """
        Initialize the builder settings.
        """
        super(AdvancedBuilderSettings, self).__init__()
        self._window = window

        # Load the relevant settings
        self.package_settings = sublime.load_settings(AdvancedBuilderSettings.SETTINGS_FILE)
        self.project_settings = window.active_view().settings()
        self.build_settings = {}
        self._project = None
        self._active_file = window.active_view().file_name()
        self._init_commands()
        self._init_build_phases()
        self._init_package_defaults()
        self._init_paths()

    def _init_commands(self):
        """
        Get a particular value for a key.
        """
        commands_node = self.package_settings.get("commands")
        if(commands_node is None):
            sublime.error_message("No commands specified. Please check your ABS build system configuration.")
            return None

        if(not isinstance(commands_node, dict)):
            sublime.error_message("Command specification has a wrong format. Please check your ABS build system configuration.")
            return None

        # Use the platform-specific config by default.
        commands = commands_node.get(sublime.platform())

        if(isinstance(commands, dict)):
            # This is the platform-specific definition for commands.
            self._commands = commands
        else:
            # Fall back to the non-platform-specific definition.
            self._commands = commands_node

    def _init_build_phases(self):
        """
        Initialize the build phases.
        """
        self._build_phases = self.project_settings.get("advanced_build_phases", {})
        if(not isinstance(self._build_phases, list)):
            # Not a valid config, get out
            self._build_phases = []
            sublime.error_message("Wrong format build phase definitions. Please check your project configuration.")

    def _init_package_defaults(self):
        self.package_defaults = self.package_settings.get("defaults")

        if(self.package_defaults is None):
            self.package_defaults = {}

    def command(self, name):
        """
        Get a command by name, resolving all its settings.

        @param name The string name of the command.
        @returns The list of command parts for the current platform.
        """

        # this should be a dictionary, filled with execution-specific values.
        command = self._commands.get(name)

        if(command is None):
            return None

        if(isinstance(command, list)):
            # well, its not, its just the pure command.
            command = {
                "cmd": command
            }

        # replace all parts of the command.
        for i in range(len(command["cmd"])):
            command["cmd"][i] = self.expand_placeholders(command["cmd"][i])

        self._update_command(command, "working_dir")
        self._update_command(command, "file_regex")
        self._update_command(command, "line_regex")

        return command

    def _update_command(self, command, key):
        """
        Update a specific value in the command dictionary.
        """
        value = command.get(key)
        if(value is None):
            value = self.build_settings.get(key)

            if(value is None):
                value = self.package_defaults.get(key)

        if(value is not None):
            command[key] = self.expand_placeholders(value)

    def build_phases(self):
        """
        Get all configured phases from the active views settings
        """
        return self._build_phases

    def active_configuration(self):
        """
        Returns the currently active configuration
        """
        return self.build_settings.get("configuration")

    def active_task(self):
        """
        Returns the currently active task
        """
        task = self.build_settings.get("task")
        if(task is None):
            task = "Build"

        return task

    def active_file(self):
        """
        Return the file, currently being displayed in the editor.
        """
        return self._active_file

    def build_all(self):
        """
        Returns whether or not all the phases should be built
        """
        value = self.build_settings.get("build_all")
        return (value is not None) and value

    def quiet(self):
        """
        Get whether the user requested a quiet run or not.
        """
        value = self.build_settings.get("quiet")
        return (value is not None) and value

    def jump_to_error(self):
        """
        Get whether the user wants to jump directly to the first
        result after the build completes
        """
        value = self.build_settings.get("jump_to_error")
        return (value is None) or value

    def project(self):
        """
        Get the project settings.
        """
        if(self._project is None):
            if(self._project_file is None):
                return None

            with open(self._project_file) as fd:
                self._project = json.load(fd)
                self._project_dirty = False

        return self._project

    def project_dirty(self):
        self._project_dirty = True

    def save_project(self):
        if(self._project is None):
            return

        if(not self._project_dirty):
            return

        saver = SettingsWriter(self._window, self._project_file, self._project)
        saver.save()

    def _init_paths(self):
        self._project_path = None
        self._project_file = None
        self._current_folder = None
        self._scanned_folders = []
        self._package_path = os.path.join(sublime.packages_path(), "Advanced Build System")
        #self._package_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        for folder in self._window.folders():
            if(self._project_file is None):
                self._find_project(folder)

            if(self._current_folder is None) and (self._window.active_view().file_name().startswith(folder)):
                self._current_folder = folder

        if(self._project_file is None):
            self._project_path = "."
        else:
            self._project_path = os.path.dirname(self._project_file)

        if(self._current_folder is None):
            self._current_folder = "."

        del(self._scanned_folders)

    def _find_project(self, folder):
        path = os.path.abspath(folder)
        depth = AdvancedBuilderSettings.PROJECT_PATH_RECURSION_DEPTH
        while(self._project_file is None) and (depth >= 0):
            self._project_file = self._find_project_downwards(path, depth)
            path = os.path.abspath(os.path.join(path, ".."))
            depth -= 1

    def _find_project_downwards(self, path, remaining_depth):
        if(path in self._scanned_folders) or (remaining_depth < 0):
            # Either we were already here or the maximum
            # recursion depth was reached.
            return None

        # keep a list of where you were, because we are moving
        # up the tree and we do not want to do work twice.
        self._scanned_folders.append(path)

        for entry in os.listdir(path):
            if(entry == ".") or (entry == ".."):
                continue

            entry_path = os.path.join(path, entry)
            if(os.path.isdir(entry_path)):
                found = self._find_project_downwards(entry_path, remaining_depth - 1)
                if(found is not None):
                    # Get out directly, we found something.
                    return found
            elif(entry.endswith(".sublime-project")) and (self._evaluate_settings_file(entry_path)):
                return entry_path

    def _evaluate_settings_file(self, path):
        # just take it, its within reach and we scanned into the structure
        # before we went outwards, so this is probably the closest we get!
        return True

    def expand_placeholders(self, value, checkExists=True):
        """
        Expand the placeholders in values (taken from the CompleteSharp plugin
        and modified to also expand ${package}).

        @param value The value to expand place-holders in.
        @param file_exists If true, paths will only be returned, if they exist
        """
        get_existing_files = \
            lambda m: [path \
                for f in self._window.folders() \
                for path in [os.path.join(f, m.group('file'))] \
                if checkExists and os.path.exists(path) or not checkExists
            ]
        value = re.sub(r'\${project_path:(?P<file>[^}]+)}', lambda m: len(get_existing_files(m)) > 0 and get_existing_files(m)[0] or m.group('file'), value)
        value = re.sub(r'\${env:(?P<variable>[^}]+)}', lambda m: os.getenv(m.group('variable')) if os.getenv(m.group('variable')) else "%s_NOT_SET" % m.group('variable'), value)
        value = re.sub(r'\${home}', os.getenv('HOME') if os.getenv('HOME') else "HOME_NOT_SET", value)
        value = re.sub(r'\${folder:(?P<file>[^}]+)}', lambda m: os.path.dirname(m.group('file')), value)
        value = re.sub(r'\${project_path}', self._project_path, value)
        value = re.sub(r'\${folder}', self._current_folder, value)
        value = re.sub(r'\${configuration}', self.active_configuration(), value)
        value = re.sub(r'\${package}', self._package_path, value)
        value = re.sub(r'\${task:(?P<variable>[^}]+)}', lambda m: m.group("variable") if self.active_task() is None else self.active_task(), value)
        value = value.replace('\\', '/')

        return value

