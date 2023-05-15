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
import threading
import subprocess
import functools
import time
import sublime
import sublime_plugin

if int(sublime.version()) < 3000:
    from common import AdvancedBuilderSettings
    from build_phases import BuildSolutionPhase, BuildUnitySolutionPhase, CopyFilesPhase, StyleCopPhase, RunCommandPhase
else:
    from .common import AdvancedBuilderSettings
    from .build_phases import BuildSolutionPhase, BuildUnitySolutionPhase, CopyFilesPhase, StyleCopPhase, RunCommandPhase
def printcons(*msg):
    print(" ".join(str(x) for x in msg))

supported_build_phases = {
    "solution": BuildSolutionPhase,
    "unity": BuildUnitySolutionPhase,
    "copy": CopyFilesPhase,
    "stylecop": StyleCopPhase,
    "command": RunCommandPhase
}

def value_or_default(dictionary, key, expect_type, default):
    value = dictionary.get(key)
    if(value is None) or ((expect_type is not None) and (not isinstance(value, expect_type))):
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
    def __init__(self, cmd, shell_cmd, env, listener,
            # "path" is an option in build systems
            path="",
            # "shell" is an options in build systems
            shell=False,
            **kwargs):

        if not shell_cmd and not cmd:
            raise ValueError("shell_cmd or cmd is required")

        if shell_cmd and not isinstance(shell_cmd, str):
            raise ValueError("shell_cmd must be a string")

        # The process-specific output configuration
        self.skip_lines = value_or_default(kwargs, "skip_lines", int, 0)
        self.working_dir = value_or_default(kwargs, "working_dir", None, "")
        self.error_regex = value_or_default(kwargs, "error_regex", None, None)
        self.warning_regex = value_or_default(kwargs, "warning_regex", None, None)
        self.message_regex = value_or_default(kwargs, "message_regex", None, None)
        self.hide_regex = value_or_default(kwargs, "hide_regex", None, None)
        self.line_regex = value_or_default(kwargs, "line_regex", None, None)
        self.warnings_as_errors = value_or_default(kwargs, "warnings_as_errors", bool, False)
        self.allow_hide_errors = value_or_default(kwargs, "allow_hide_errors", bool, False)
        self.completion_callback = kwargs.get("completion_callback")

        if self.error_regex is not None:
            self.error_re = self.make_re(self.error_regex)
        if self.warning_regex is not None:
            self.warning_re = self.make_re(self.warning_regex)
        if self.message_regex is not None:
            self.message_re = self.make_re(self.message_regex)
        if self.line_regex is not None:
            self.line_re = self.make_re(self.line_regex)
        if self.hide_regex is not None:
            self.hide_re = self.make_re(self.hide_regex)

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
        for k in proc_env:
            if sys.platform == "win32" and int(sublime.version()) >= 3000:
                proc_env[k] = os.path.expandvars(proc_env[k])
            else:
                proc_env[k] = os.path.expandvars(proc_env[k]).encode(sys.getfilesystemencoding())

        if shell_cmd:
            printcons("Executing %s" % shell_cmd)
        else:
            printcons("Executing %s" % " ".join(cmd))

        if shell_cmd and sys.platform == "win32":
            # Use shell=True on Windows, so shell_cmd is passed through with the correct escaping
            self.proc = subprocess.Popen(shell_cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, shell=True)
        elif shell_cmd and sys.platform == "darwin":
            # Use a login shell on OSX, otherwise the users expected env vars won't be setup
            self.proc = subprocess.Popen(["/bin/bash", "-l", "-c", shell_cmd], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, shell=False)
        elif shell_cmd and sys.platform == "linux":
            # Explicitly use /bin/bash on Linux, to keep Linux and OSX as
            # similar as possible. A login shell is explicitly not used for
            # linux, as it's not required
            self.proc = subprocess.Popen(["/bin/bash", "-c", shell_cmd], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, shell=False)
        else:
            # Old style build system, just do what it asks
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, shell=shell)

        if path:
            os.environ["PATH"] = old_path

        if self.proc.stdout:
            threading.Thread(target=self.read_stdout).start()

        if self.proc.stderr:
            threading.Thread(target=self.read_stderr).start()

    def make_re(self, expr):
        if type(expr) is list:
            return [re.compile(regex, re.UNICODE) for regex in expr]
        else:
            return re.compile(expr, re.UNICODE)

    def kill(self):
        if not self.killed:
            self.killed = True
            if sys.platform == "win32":
                # terminate would not kill process opened by the shell cmd.exe, it will only kill
                # cmd.exe leaving the child running
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.Popen("taskkill /PID " + str(self.proc.pid), startupinfo=startupinfo)
            else:
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

            if len(data) > 0:
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

            if len(data) > 0:
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stderr.close()
                break

class OutputWindowController(ProcessListener):
    def init(self, command, task, encoding = "utf-8", quiet = False, jump_to_error = True, syntax = "Packages/Advanced Build System/AdvancedBuilderConsole.tmLanguage"):
        self.window = command.window
        self.task = task

        if not hasattr(self, 'output_view'):
            # Try not to call get_output_panel until the regexes are assigned
            if int(sublime.version()) < 3000:
                self.output_view = self.window.get_output_panel("advanced_builder")
            else:
                self.output_view = self.window.create_output_panel("advanced_builder")

        self.working_dir = os.path.dirname(self.window.active_view().file_name())
        for folder in self.window.folders():
            if(self.working_dir.startswith(folder)):
                self.working_dir = folder
                break;

        self.output_view.settings().set("result_file_regex", "^\[[A-Z\s_]+\]: ([a-zA-Z0-9\\\/\s\:\._-]+)\s\((\d+),\s(\d+)\):\s.*$")
        self.output_view.settings().set("result_line_regex", "^.*\((\d+),\s(\d+)\).*$")
        self.output_view.settings().set("result_base_dir", self.working_dir)

        if int(sublime.version()) < 3000:
            # Call get_output_panel() a second time after assigning the above
            # settings, so that it'll be picked up as a result buffer
            self.window.get_output_panel("advanced_builder")
        else:
            self.output_view.settings().set("line_numbers", False)
            self.output_view.settings().set("gutter", False)
            self.output_view.settings().set("scroll_past_end", False)
            self.output_view.assign_syntax(syntax)

            # Call create_output_panel() a second time after assigning the above
            # settings, so that it'll be picked up as a result buffer
            self.window.create_output_panel("advanced_builder")

        self.encoding = encoding
        self.quiet = quiet
        self.jump_to_error = jump_to_error

        self.proc = None
        self.has_errors = False
        self._running = False

        show_panel_on_build = sublime.load_settings("Preferences.sublime-settings").get("show_panel_on_build", True)
        if show_panel_on_build:
            self.window.run_command("show_panel", {"panel": "output.advanced_builder"})

    def run(self, cmd = None, shell_cmd = None, working_dir = "", env = {}, kill = False, **kwargs):
        self.has_errors = False

        # Mangle some parameters for the AsyncBuildProcess
        if("error_regex" not in kwargs) and ("file_regex" in kwargs):
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
            if cmd is not None:
                printcons("Running " + " ".join(cmd))
            elif shell_cmd is not None:
                printcons("Running " + shell_cmd)

            sublime.status_message("Building")

        merged_env = env.copy()
        if self.window.active_view():
            user_env = self.window.active_view().settings().get('build_env')
            if user_env:
                merged_env.update(user_env)

        # Change to the working dir, rather than spawning the process with it,
        # so that emitted working dir relative path names make sense
        if working_dir != "":
            printcons("Changing to " + working_dir)
            os.chdir(working_dir)

        err_type = OSError
        if os.name == "nt":
            err_type = WindowsError

        try:
            # Forward kwargs to AsyncBuildProcess
            self.proc = AsyncBuildProcess(cmd, shell_cmd, merged_env, self, working_dir = working_dir, **kwargs)
            self._running = True
        except(err_type) as exc:
            self.write(str(exc))
            self.write("[cmd:  " + str(cmd) + "]")
            self.write("[dir:  " + str(os.getcwd()) + "]")
            if "PATH" in merged_env:
                self.write("[path: " + str(merged_env["PATH"]) + "]")
            else:
                self.write("[path: " + str(os.environ["PATH"]) + "]")
            if not self.quiet:
                self.write("[Finished]")

    def is_enabled(self, kill = False):
        if kill:
            return hasattr(self, 'proc') and self.proc and self.proc.poll()
        else:
            return True

    def is_running(self):
        return self._running

    def write(self, message):
        self.append_data(None, (message + "\n").encode(self.encoding))

    def process_print(self, message):
        if(not self.quiet):
            printcons(message)
        self.append_data(self.proc, (message + "\n").encode(self.encoding))

    def _build_message(self, proc, importance, **kwargs):
        message = ""
        # Add the importance to the arguments
        if(importance is not None):
            kwargs["importance"] = importance
            message = "[%(importance)s]:"

        path = kwargs.get("file")
        if(path is not None):
            # There is a path, make sure it is relative
            path = self.get_relative_path(self.working_dir, path)
            kwargs["file"] = path

            # Add the file information and look for lines
            message += " %(file)s"
            line = kwargs.get("line")
            column = kwargs.get("column")

            if(line is not None):
                if(column is None):
                    # Use 0 as default column for jump-to-line support
                    kwargs["column"] = 0

                # Add the file and line placeholders to the message
                message += " (%(line)s, %(column)s):"

        for message_pos in ["message_pre", "message", "message_post"]:
            if(kwargs.get(message_pos) is not None):
                message += " %(" + message_pos + ")s"

        message = message.strip()
        message = message % kwargs
        message = message.replace("$n$", " ")
        return message

    def write_to_view(self, edit, message, focus, **args):
        #printcons(message)
        if int(sublime.version()) < 3000:
            self.output_view.insert(edit, self.output_view.size(), unicode(message))
        else:
            self.output_view.run_command('append', {'characters': message, 'force': True, 'scroll_to_end': focus})

    def begin_edit(self):
        if int(sublime.version()) < 3000:
            self.output_view.set_read_only(False)
            return self.output_view.begin_edit()
        else:
            return None

    def end_edit(self, edit, selection_was_at_end):
        if int(sublime.version()) < 3000:
            if selection_was_at_end:
                self.output_view.show(self.output_view.size())
            self.output_view.end_edit(edit)
            self.output_view.set_read_only(True)

    def match_line(self, line, expr):
        if(type(expr) is list):
            for regex in expr:
                match = regex.match(line)
                if(match is not None):
                    return match
        else:
            return expr.match(line);

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

        edit = self.begin_edit();

        # Prepare the data
        if(proc is not None):
            str_data = proc.buffer + str_data
            proc.buffer = ""

        str_lines = str_data.split("\n")
        if(len(str_lines) > 0):
            if(proc is not None and str_lines[-1] != ""):
                # Got a line, that was not terminated, put it in the buffer and remove it.
                proc.buffer = str_lines[-1]

            del(str_lines[-1])

        # walk through the lines
        for line in str_lines:
            if(proc is None):
                self.write_to_view(edit, line + "\n", selection_was_at_end)
                continue

            # process the process-specific stuff O.o
            if(proc.skip_lines > 0):
                # Skipping this line
                proc.skip_lines -= 1
                continue

            if(line == ""):
                # The temporary buffer is empty, just start processing a new line
                continue

            if(proc.line_regex is not None):
                line_match = self.match_line(line, proc.line_re)
                if(line_match is not None):
                    # This is still a new part of the line
                    line_data = line_match.groupdict()
                    line_message = "$n$" + self._build_message(proc, None, **line_data)
                    printcons(line_message)
                    self.temp_str += line_message
                    continue

            self.process_line(edit, proc, self.temp_str, selection_was_at_end)
            self.temp_str = line

        self.end_edit(edit, selection_was_at_end)

    def process_line(self, edit, proc, line, selection_was_at_end):
        hide = False
        if(proc.hide_regex is not None):
            # check, if the message needs to be hidden
            hide_match = self.match_line(line, proc.hide_re)
            if(hide_match is not None):
                hide = True

        if(not hide):
            printcons(line)

        if(proc.error_regex is not None):
            # got an error regex, match it
            err_match = self.match_line(line, proc.error_re)

            if(err_match is not None):
                self.has_errors = True
                if(not proc.allow_hide_errors or not hide):
                    printcons("Error in: %s" % line.strip())
                    error_data = err_match.groupdict()
                    line = self._build_message(proc, "ERROR", **error_data)
                    self.write_to_view(edit, line + "\n", selection_was_at_end)

                return

        if(proc.warning_regex is not None):
            # got a warning regex
            warn_match = self.match_line(line, proc.warning_re)

            if(warn_match is not None):
                warning_data = warn_match.groupdict()

                if(proc.warnings_as_errors):
                    self.has_errors = True
                    if(not proc.allow_hide_errors or not hide):
                        printcons("Warning in: %s" % line.strip())
                        line = self._build_message(proc, "ERROR", **warning_data)
                        self.write_to_view(edit, line + "\n", selection_was_at_end)
                elif(not hide):
                    printcons("Warning in: %s" % line.strip())
                    line = self._build_message(proc, "WARNING", **warning_data)
                    self.write_to_view(edit, line + "\n", selection_was_at_end)

                return

        if(proc.message_regex is not None):
            # got an error regex, match it
            msg_match = self.match_line(line, proc.message_re)

            if(msg_match is not None):
                if(not hide):
                    printcons("Message in: %s" % line.strip())
                    line = self._build_message(proc, None, **msg_match.groupdict())
                    self.write_to_view(edit, line + "\n", selection_was_at_end)

                return

        if(not self.quiet):
            self.write_to_view(edit, line + "\n", selection_was_at_end)

    def finish_data(self, proc):
        selection_was_at_end = (len(self.output_view.sel()) == 1
            and self.output_view.sel()[0]
                == sublime.Region(self.output_view.size()))
        edit = self.begin_edit();
        self.process_line(edit, proc, self.temp_str, selection_was_at_end)
        self.end_edit(edit, selection_was_at_end)

    def get_relative_path(self, working_dir, path):
        return os.path.relpath(path, working_dir)
        #common_prefix = os.path.commonprefix([working_dir, path])
        #return os.path.relpath(path, common_prefix).replace(os.path.sep, "/")

    def finish(self, proc):
        if proc != self.proc:
            return

        if(proc.exit_code() is not None) and (proc.exit_code() != 0):
            self.has_errors = True

        if(proc.completion_callback is not None):
            printcons("Running completion callback")
            if(proc.completion_callback(self)):
                self.has_errors = True

        self._running = False

    def done(self):
        if int(sublime.version()) < 3000:
            edit = self.output_view.begin_edit()
            self.output_view.sel().clear()
            self.output_view.sel().add(sublime.Region(0))
            self.output_view.end_edit(edit)

        # Set the selection to the start, so that next_result will work as expected
        if(self.jump_to_error):
            self.window.run_command("next_result", None)

        errs = self.output_view.find_all_results()
        message = ""
        if(len(errs) != 0):
            message = "[%s finished with %d errors]" % (self.task, len(errs))
            self.has_errors = True
        elif(self.has_errors):
            message = "[%s finished with errors]" % (self.task)
            self.has_errors = True
        else:
            message = "[%s successful]" % (self.task)

        self.write(message)
        sublime.status_message(message)

    def kill(self):
        if self.proc is not None:
            self.proc.kill()
            self.proc = None

        if int(sublime.version()) < 3000:
            edit = self.output_view.begin_edit()
            self.output_view.sel().clear()
            self.output_view.sel().add(sublime.Region(0))
            self.output_view.end_edit(edit)

        self.output_view.find_all_results()

        message = "[%s interrupted]" % (self.task)
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
    PHASE_SOLUTION = "unity_project"
    PHASE_COPY = "copy"
    PHASE_STYLECOP = "stylecop"
    PHASE_COMMAND = "command"
    RUN_ASYNC = True

    def run(self, **args):
        """
        Run the command. This is called by sublime, when a build is executed.
        """
        kill = args.get("kill")
        if(kill is not None) and (kill):
            # Kill the currently running process and get out
            if(hasattr(self, "_exec")) and (self._exec is not None):
                printcons("Killing current task")
                self.cancel_command()
            else:
                printcons("No task to kill")

            return

        if(hasattr(self, "_exec")) and (self._exec is not None):
            # There is a command already running, ask if it should be stopped
            stop = sublime.ok_cancel_dialog("There is already a command being processed, do you want to cancel it?", "Stop")
            if(stop):
                # Stop the old process and continue to use the new one
                self.cancel_command()
            else:
                # Get out, there should only be one build running
                return

        self.run_command(**args)

    def cancel_command(self):
        self._exec.kill()
        self._stop = True
        if(not self._quiet):
            self._exec.write("Killed: %s [%s]" % (self._current_phase, self._settings.active_configuration()))
        self._cleanup_command()

    def run_command(self, **args):
        # Initialize a settings wrapper (because we have so many!)
        self._settings = AdvancedBuilderSettings(self.window, args)
        self._exec = OutputWindowController()
        self._exec.init(self, self._settings.active_task(), jump_to_error = self._settings.jump_to_error())
        self._current_phase = None
        self._quiet = self._settings.quiet()
        self._exec.quiet = self._quiet
        self._stop = False

        # Get the phases
        self._phases = []
        for phase_config in self._settings.build_phases():
            phase = self._get_phase_object(phase_config)
            printcons("Evaluating phase ", phase)
            if(phase is None) or (not phase.is_valid()):
                self._exec.write("Invalid config for phase: %s ([%s]), aborting" % (phase_config.get("name"), str(phase)))
                return

            self._phases.append(phase)

        # Run it this way, to not run into concurrency issues.
        sublime.set_timeout(self._run_tasks, 200)

    def _cleanup_command(self):
        self._exec = None
        self._settings = None
        self._phases = None
        self._current_phase = None

    def _run_tasks(self):
        """
        Run all tasks sequentially.
        """
        if(self._stop):
            # Now it gets funky: If a process was killed, the new one
            # will spawn a new _run_tasks method. That would mean we
            # have two. But because this method does not hold a context
            # by itself, we don't care, which of the two is stopped, it
            # will be the first one to come in here. Care must be taken
            # however on when to clean up the _exec context, which needs
            # to happen when _stop is set to True, so as to not screw up
            # the context of the new process.
            self._stop = False
            return

        if(self._exec.is_running()):
            # Still waiting for the process to finish, wait another 0.1s
            sublime.set_timeout(self._run_tasks, 100)
            return

        if(len(self._phases) < 1):
            # We are done
            self._exec.done()
            self._cleanup_command()
            return;

        if(self._exec.has_errors) and (self._current_phase is not None) and (self._current_phase.stop_on_error):
            # Don't start the next one, this one broke.
            if(not self._quiet):
                self._exec.write("%s [%s] has errors, stopping" % (self._current_phase, self._settings.active_configuration()))
            self._exec.done()
            self._cleanup_command()
            return

        # The last phase finished successfully, start a new one.
        started = False
        while(not started):
            if(len(self._phases) < 1):
                self._exec.done()
                self._cleanup_command()
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
        # Resolve the type of the phase
        phase_type = phase_config.get("type")
        if(phase_type is None):
            return None

        # Resolve the class of the type
        phase_class = supported_build_phases.get(phase_type)
        if(phase_class is None):
            return None

        phase = phase_class()
        phase.init(self._settings, **phase_config)
        return phase
