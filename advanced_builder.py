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
An "advanced" (as in more flexible than what's already there)
build system for the Sublime Text 2 editor.
"""

import sys
import re
import os
import os.path
import thread
import subprocess
import functools
import time
import sublime
import sublime_plugin

from common.build_phase import BuildPhase
from common.settings import AdvancedBuilderSettings
from build_phases.build_solution_phase import BuildSolutionPhase
from build_phases.copy_files_phase import CopyFilesPhase
from build_phases.stylecop_phase import StyleCopPhase
from build_phases.run_command_phase import RunCommandPhase

def value_or_default(dictionary, key, expect_type, default):
    value = dictionary.get(key)
    if(value is None) or (not isinstance(value, expect_type)):
        value = default
    return value

class ProcessListener(object):
    def on_data(self, proc, data):
        pass

    def on_finished(self, proc):
        pass

# Encapsulates subprocess.Popen, forwarding stdout to a supplied
# ProcessListener (on a separate thread)
class AsyncBuildProcess(object):
    def __init__(self, arg_list, env, listener,
            # "path" is an option in build systems
            path="",
            # "shell" is an options in build systems
            shell=False,
            **kwargs):

        # The process-specific output configuration
        self.skip_lines = value_or_default(kwargs, "skip_lines", long, 0)
        self.working_dir = value_or_default(kwargs, "working_dir", unicode, "")
        self.error_regex = value_or_default(kwargs, "error_regex", unicode, None)
        self.warning_regex = value_or_default(kwargs, "warning_regex", unicode, None)
        self.line_regex = value_or_default(kwargs, "line_regex", unicode, None)
        self.warnings_as_errors = value_or_default(kwargs, "warnings_as_errors", bool, False)
        self.completion_callback = kwargs.get("completion_callback")

        # The output buffer, because the regex matching will require full lines
        self.buffer = ""

        self.listener = listener
        self.killed = False

        self.start_time = time.time()

        # Hide the console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Set temporary PATH to locate executable in arg_list
        if path:
            old_path = os.environ["PATH"]
            # The user decides in the build system whether he wants to append $PATH
            # or tuck it at the front: "$PATH;C:\\new\\path", "C:\\new\\path;$PATH"
            os.environ["PATH"] = os.path.expandvars(path).encode(sys.getfilesystemencoding())

        proc_env = os.environ.copy()
        proc_env.update(env)
        for k, v in proc_env.iteritems():
            proc_env[k] = os.path.expandvars(v).encode(sys.getfilesystemencoding())

        # Start a process and return immediately
        self.proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, shell=shell)

        if path:
            os.environ["PATH"] = old_path

        if self.proc.stdout:
            thread.start_new_thread(self.read_stdout, ())

        if self.proc.stderr:
            thread.start_new_thread(self.read_stderr, ())

    def kill(self):
        if not self.killed:
            self.killed = True
            self.proc.terminate()
            self.listener = None

    def wait(self):
        if not self.killed:
            self.proc.wait()

    def poll(self):
        return self.proc.poll() == None

    def exit_code(self):
        return self.proc.poll()

    def read_stdout(self):
        while True:
            data = os.read(self.proc.stdout.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stdout.close()
                if self.listener:
                    self.listener.on_finished(self)
                break

    def read_stderr(self):
        while True:
            data = os.read(self.proc.stderr.fileno(), 2**15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stderr.close()
                break

class OutputWindowController(ProcessListener):
    def init(self, command, encoding = "utf-8", quiet = False, jump_to_error = True):
        self.window = command.window

        if not hasattr(self, 'output_view'):
            # Try not to call get_output_panel until the regexes are assigned
            self.output_view = self.window.get_output_panel("advanced_builder")

        working_dir = os.path.dirname(self.window.active_view().file_name())
        self.output_view.settings().set("result_file_regex", "^\[[A-Z]+\]: ([\/\d\w:\\\.-]*) \((\d+), (\d+)\):\s.*$")
        self.output_view.settings().set("result_line_regex", "^.*\((\d+), (\d+)\).*$")
        self.output_view.settings().set("result_base_dir", working_dir)

        # Call get_output_panel a second time after assigning the above
        # settings, so that it'll be picked up as a result buffer
        self.window.get_output_panel("advanced_builder")

        show_panel_on_build = sublime.load_settings("Preferences.sublime-settings").get("show_panel_on_build", True)
        if show_panel_on_build:
            self.window.run_command("show_panel", {"panel": "output.advanced_builder"})

        self.encoding = encoding
        self.quiet = quiet
        self.jump_to_error = jump_to_error

        self.proc = None
        self.has_errors = False
        self._running = False

    def run(self, cmd = [], working_dir = "", env = {}, kill = False, **kwargs):
        self.has_errors = False

        # Mangle some parameters for the AsyncBuildProcess
        if(not kwargs.has_key("error_regex")) and (kwargs.has_key("file_regex")):
            # Support sublime-specific error finding
            kwargs["error_regex"] = kwargs["file_regex"]
            del(kwargs["file_regex"])

        if kill:
            if self.proc and self.proc.poll():
                # Kill the old process, that still seems to be running
                self.proc.kill()
                self.proc = None
                self.append_data(None, "[Cancelled]")

        # Default to the current files directory if no working directory was given
        if (working_dir == "" and self.window.active_view()
                        and self.window.active_view().file_name()):
            working_dir = os.path.dirname(self.window.active_view().file_name())

        if not self.quiet:
            print "Running " + " ".join(cmd)
            sublime.status_message("Building")

        merged_env = env.copy()
        if self.window.active_view():
            user_env = self.window.active_view().settings().get('build_env')
            if user_env:
                merged_env.update(user_env)

        # Change to the working dir, rather than spawning the process with it,
        # so that emitted working dir relative path names make sense
        if working_dir != "":
            os.chdir(working_dir)

        err_type = OSError
        if os.name == "nt":
            err_type = WindowsError

        try:
            # Forward kwargs to AsyncBuildProcess
            self.proc = AsyncBuildProcess(cmd, merged_env, self, working_dir = working_dir, **kwargs)
            self._running = True
        except err_type as e:
            self.append_data(None, str(e) + "\n")
            self.append_data(None, "[cmd:  " + str(cmd) + "]\n")
            self.append_data(None, "[dir:  " + str(os.getcwdu()) + "]\n")
            if "PATH" in merged_env:
                self.append_data(None, "[path: " + str(merged_env["PATH"]) + "]\n")
            else:
                self.append_data(None, "[path: " + str(os.environ["PATH"]) + "]\n")
            if not self.quiet:
                self.append_data(None, "[Finished]")

    def is_enabled(self, kill = False):
        if kill:
            return hasattr(self, 'proc') and self.proc and self.proc.poll()
        else:
            return True

    def is_running(self):
        return self._running

    def write(self, message):
        self.append_data(None, str(message) + "\n")

    def process_print(self, message):
        if(not self.quiet):
            print message
        self.append_data(self.proc, message + "\n")

    def _build_message(self, proc, importance, **kwargs):
        # Add the importance to the arguments
        kwargs["importance"] = importance
        message = "[%(importance)s]"

        path = kwargs.get("file")
        if(path is not None):
            # There is a path, make sure it is relative
            path = self.get_relative_path(proc.working_dir, path)
            kwargs["file"] = path

            # Add the file information and look for lines
            message += ": %(file)s"
            line = kwargs.get("line")
            column = kwargs.get("column")

            if(line is not None):
                if(column is None):
                    # Use 0 as default column for jump-to-line support
                    kwargs["column"] = 0

                # Add the file and line placeholders to the message
                message += " (%(line)s, %(column)s):"

        message += " %(message)s"
        return message % kwargs

    def append_data(self, proc, data):
        if(proc is not None) and (proc != self.proc):
            # This is not our current process, don't do anything.
            return

        try:
            str_data = data.decode(self.encoding)
        except:
            str_data = "[Decode error - output not " + self.encoding + "]\n"
            proc = None

        # Normalize newlines, Sublime Text always uses a single \n separator
        # in memory.
        str_data = str_data.replace('\r\n', '\n').replace('\r', '\n')
        selection_was_at_end = (len(self.output_view.sel()) == 1
            and self.output_view.sel()[0]
                == sublime.Region(self.output_view.size()))
        self.output_view.set_read_only(False)
        edit = self.output_view.begin_edit()

        # Prepare the data
        if(proc is not None):
            str_data = proc.buffer + str_data
            proc.buffer = ""

        str_lines = str_data.split("\n")
        if(len(str_lines) > 0):
            if(str_lines[-1] != ""):
                # Got a line, that was not terminated, put it in the buffer and remove it.
                proc.buffer = str_lines[-1]

            del(str_lines[-1])

        # walk through the lines
        for line in str_lines:
            if(proc is None):
                self.output_view.insert(edit, self.output_view.size(), unicode(line + "\n"))
                continue

            # process the process-specific stuff O.o
            if(proc.skip_lines > 0):
                # Skipping this line
                proc.skip_lines -= 1
                continue

            if(proc.error_regex is not None):
                # got an error regex, match it
                err_match = re.match(str(proc.error_regex), line, re.UNICODE)

                if(err_match is not None):
                    print "Error in: %s" % line.strip()
                    error_data = err_match.groupdict()
                    self.has_errors = True
                    line = self._build_message(proc, "ERROR", **error_data)
                    self.output_view.insert(edit, self.output_view.size(), unicode(line + "\n"))
                    continue

            if(proc.warning_regex is not None):
                # got a warning regex
                warn_match = re.match(str(proc.warning_regex), line, re.UNICODE)

                if(warn_match is not None):
                    print "Warning in: %s" % line.strip()
                    warning_data = warn_match.groupdict()

                    if(proc.warnings_as_errors):
                        self.has_errors = True
                        line = self._build_message(proc, "ERROR", **warning_data)
                    else:
                        line = self._build_message(proc, "WARNING", **warning_data)

                    self.output_view.insert(edit, self.output_view.size(), unicode(line + "\n"))
                    continue

            if(not self.quiet):
                self.output_view.insert(edit, self.output_view.size(), unicode(line + "\n"))

        if selection_was_at_end:
            self.output_view.show(self.output_view.size())
        self.output_view.end_edit(edit)
        self.output_view.set_read_only(True)

    def get_relative_path(self, working_dir, path):
        common_prefix = os.path.commonprefix([working_dir, path])
        return os.path.relpath(path, common_prefix)

    def finish(self, proc):
        if proc != self.proc:
            return

        if(proc.exit_code() is not None) and (proc.exit_code() != 0):
            self.has_errors = True

        if(proc.completion_callback is not None):
            print "Running completion callback"
            if(proc.completion_callback(self)):
                self.has_errors = True

        self._running = False

    def done(self):
        # Set the selection to the start, so that next_result will work as expected
        edit = self.output_view.begin_edit()
        self.output_view.sel().clear()
        self.output_view.sel().add(sublime.Region(0))
        self.output_view.end_edit(edit)

        if(self.jump_to_error):
            self.window.run_command("next_result", None)

        errs = self.output_view.find_all_results()
        message = ""
        if(len(errs) != 0):
            message = "[Build finished with %d errors]" % len(errs)
            self.has_errors = True
        elif(self.has_errors):
            message = "[Build finished with errors]"
            self.has_errors = True
        else:
            message = "[Build successful]"

        self.write(message)
        sublime.status_message(message)

    def on_data(self, proc, data):
        # Return data to the main thread from the output and error threads
        sublime.set_timeout(functools.partial(self.append_data, proc, data), 0)

    def on_finished(self, proc):
        # Tell the execution command, that this one finished
        # from the output and error threads
        sublime.set_timeout(functools.partial(self.finish, proc), 0)

class AdvancedBuilderCommand(sublime_plugin.WindowCommand):
    """
    The sublime plugin command class.
    """

    PHASE_SOLUTION = "solution"
    PHASE_COPY = "copy"
    PHASE_STYLECOP = "stylecop"
    PHASE_COMMAND = "command"
    RUN_ASYNC = True

    def run(self, **args):
        """
        Run the command. This is called by sublime, when a build is executed.
        """
        # Initialize a settings wrapper (because we have so many!)
        self._settings = AdvancedBuilderSettings(self.window)
        self._settings.build_settings = args;
        self._exec = OutputWindowController()
        self._exec.init(self, jump_to_error = self._settings.jump_to_error())
        self._current_phase = None
        self._quiet = self._settings.quiet()
        self._exec.quiet = self._quiet

        # Get the phases
        self._phases = []
        for phase_config in self._settings.build_phases():
            phase = self._get_phase_object(phase_config)
            if(not phase.is_valid()):
                self._exec.write("Invalid config for phase: [%s], aborting" % (str(phase)))
                return

            self._phases.append(phase)

        self._run_tasks()

    def _run_tasks(self):
        """
        Run all tasks sequentially.
        """
        if(self._exec.is_running()):
            # Still waiting for the process to finish, wait another 0.1s
            sublime.set_timeout(self._run_tasks, 100)
            return

        if(len(self._phases) < 1):
            # We are done
            self._exec.done()
            return;

        if(self._exec.has_errors) and (self._current_phase is not None) and (self._current_phase.stop_on_error):
            # Don't start the next one, this one broke.
            if(not self._quiet):
                self._exec.write("%s [%s] has errors, stopping" % (self._current_phase, self._settings.active_configuration()))
            self._exec.done()
            return

        # The last phase finished successfully, start a new one.
        started = False
        while(not started):
            if(len(self._phases) < 1):
                self._exec.done()
                return;

            self._current_phase = self._phases[0]
            self._phases = self._phases[1:]

            # Start the next phase and poll for its completion
            started = self._run_new_phase(self._current_phase)

        # Wait for 0.2s before checking again
        sublime.set_timeout(self._run_tasks, 200)

    def _run_new_phase(self, phase):
        if(not (self._settings.build_all() or phase.should_run())):
            # A task, that doesn't apply to the configuration.
            if(not self._quiet):
                self._exec.write("Skipped: %s [%s]" % (phase, self._settings.active_configuration()))
            return False

        task = phase.get_task()
        if(task is None):
            # The task had errors on building its run configuration, get out!
            return False;

        self._exec.write("%s [%s]" % (phase, self._settings.active_configuration()))
        self._exec.run(**task)
        return self._exec.is_running()

    def _get_phase_object(self, phase_config):
        """
        Get a BuildPhase object for the type of the build phase.

        @returns The appropriet, initialized phase for the configured type or None, if none exists.
        """
        phase_type = phase_config.get("type")

        phase = None
        if(phase_type == AdvancedBuilderCommand.PHASE_COPY):
            phase = CopyFilesPhase()
        elif(phase_type == AdvancedBuilderCommand.PHASE_SOLUTION):
            phase = BuildSolutionPhase()
        elif(phase_type == AdvancedBuilderCommand.PHASE_STYLECOP):
            phase = StyleCopPhase()
        elif(phase_type == AdvancedBuilderCommand.PHASE_COMMAND):
            phase = RunCommandPhase()
        else:
            #sublime.error_message("Unknown build phase type: " + phase_type + " ignoring it!")
            return None

        phase.init(self._settings, **phase_config)

        return phase
