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
The .net solution build phase
"""
import re
import os.path
import sublime
if int(sublime.version()) < 3000:
    from common import BuildPhase
else:
    from ..common import BuildPhase
def printcons(*msg):
    print(" ".join(str(x) for x in msg))

from xml.dom.minidom import parse

PROJECT_RE = re.compile("^Project\(\"\{.*\}\"\) = \"(?P<project_name>.*)\", \"(?P<project_path>.*)\", \"\{.*\}\".*$")

class BuildSolutionPhase(BuildPhase):
    """
    Build phase to build a single solution.
    """

    def init(self, _settings, **kwargs):
        """
        Initialize the build phase, providing basic data.

        @param **kwargs The configuration to initialize the phase
        """
        super(BuildSolutionPhase, self).init(_settings, **kwargs)
        self._solution = kwargs.get("solution")
        self._add_assemblies = kwargs.get("add_assemblies")

        if(self._solution is None) or (self._solution == ""):
            self._invalidate("Mandatory setting 'solution' missing")

        if(self._add_assemblies is None) or (self._add_assemblies == ""):
            self._add_assemblies = True

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
            path = self._solution
            path = os.path.dirname(self.settings.expand_placeholders(path))
        else:
            path = self.settings.expand_placeholders(path)

        path = path.replace(os.path.sep, "/")
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
        command = self.settings.command("build_solution")
        if(command is None):
            self._invalidate("'build_solution' command not defined")
            return None


        command = command.copy()
        command_list = list(command["cmd"])

        solution_path = self.settings.expand_placeholders(self._solution)
        common_prefix = os.path.commonprefix([command["working_dir"], solution_path])
        solution_path = os.path.relpath(solution_path, common_prefix).replace(os.path.sep, "/")
        command_list.append(solution_path)

        command["cmd"] = command_list
        command["completion_callback"] = self.task_complete
        return command

    def task_complete(self, window_controller):
        """
        Called, when the task is completed.
        """
        if(self._add_assemblies):
            printcons("Adding assemblies")
            path = self.settings.expand_placeholders(self._solution)
            self.parse_solution(path)
            self.settings.save_project()
        else:
            printcons("Not adding assemblies, it is disabled")

        return False

    def parse_solution(self, path):
        if(not self.settings.quiet()):
            pass
        printcons("Parsing solution:", path)

        # Find all referenced projects
        solution_dir = os.path.dirname(path)

        if int(sublime.version()) < 3000:
            fd = open(path)
        else:
            fd = open(path, encoding="utf-8")

        for line in fd:
            match = PROJECT_RE.match(line)
            if(match is None):
                continue

            # Found a project entry, extract the path
            project_path = match.group("project_path")
            project_path = project_path.replace("\\", os.path.sep)

            # Make the path be relative to the solution directory and parse it
            project_path = os.path.join(solution_dir, project_path).replace(os.path.sep, "/")
            if(not self.settings.quiet()):
                pass

            if not os.path.isfile(project_path):
                continue;

            printcons("Found Project:", project_path)
            self.parse_project(project_path)

        fd.close()
        return False

    def parse_project(self, project):
        project_dir = os.path.dirname(project)
        project_xml = parse(project);
        assemblies = project_xml.getElementsByTagName("AssemblyName")

        # Find all the target assemblies
        targets = []
        for assembly in assemblies:
            extension = ".dll"
            types = assembly.parentNode.getElementsByTagName("OutputType")
            if(types[0].childNodes[0].nodeValue == "Exe"):
                extension = ".exe"
            targets.append(self.element_path(assembly) + extension)

        # Walk all output paths
        output_paths = project_xml.getElementsByTagName("OutputPath")
        for output_path in output_paths:
            opath = self.element_path(output_path)
            opath = os.path.join(project_dir, opath)
            for target in targets:
                assembly_path = os.path.join(opath, target).replace(os.path.sep, "/")
                if not self.settings.quiet():
                    pass
                printcons("Found output assembly:", assembly_path)

                self.add_assembly(assembly_path)

        # Walk through referenced assemblies
        references = project_xml.getElementsByTagName("Reference")
        for reference in references:
            hints = reference.getElementsByTagName("HintPath")
            if(hints == []):
                # Ignore empty hints, they point to packages and stuff
                # and I am currently too lazy to resolve those too.
                continue

            ref_path = self.element_path(hints[0])
            ref_path = os.path.join(project_dir, ref_path).replace(os.path.sep, "/")
            if not self.settings.quiet():
                pass
            printcons("Found referenced assembly:", ref_path)

            self.add_assembly(ref_path)

    def add_assembly(self, assembly):
        # Make sure, the absolute path to the assembly is used.
        assembly = os.path.abspath(assembly)

        # Make sure only to add assemblies, that actually exist.
        if not os.path.exists(assembly):
            printcons("Assembly not found:", assembly)
            return;

        settings_overwrite = self.settings.project().get("settings")
        if(settings_overwrite is None):
            settings_overwrite = {}

        assemblies = settings_overwrite.get("completesharp_assemblies")
        if(assemblies is None):
            assemblies = []

        if(not self._assembly_already_referenced(assemblies, assembly)):
            # So the assembly is not in the list, add it.
            printcons("Appending assembly:", assembly)
            assemblies.append(assembly)
            assemblies.sort()
            settings_overwrite["completesharp_assemblies"] = assemblies
            self.settings.project()["settings"] = settings_overwrite
            self.settings.project_dirty()

    def _assembly_already_referenced(self, assemblies, assembly):
        if(assembly in assemblies):
            # Check for exact matches real quick.
            return True

        # Check for DLL name matches in different directories, to avoid
        # CompleteSharp having more than one source.
        #for asm in assemblies:
        #    if(os.path.basename(asm) == os.path.basename(assembly)):
        #        return True

        return False

    def element_path(self, node):
        return node.childNodes[0].nodeValue.replace("\\", os.path.sep)

    def get_relative_path(self, working_dir, path):
        common_prefix = os.path.commonprefix([working_dir, path])
        return os.path.relpath(path, common_prefix)

    def __repr__(self):
        return "Solution phase: '%s' solution: '%s' configs: '%s' valid: '%s'" % (self.name, self._solution, self.configurations, self._is_valid)
