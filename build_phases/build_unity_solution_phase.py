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
The Unity3D solution build phase. It is basically the same as the standard solution
phase, but since Unity3D moves the build results from Temp/bin/ to the Library folder,
the project parser needs some additions to find those.
"""
import os.path
import sublime
from . import BuildSolutionPhase

if int(sublime.version()) < 3000:
    from common import BuildPhase
else:
    from ..common import BuildPhase
def printcons(*msg):
    print(" ".join(str(x) for x in msg))

unity_dll_locations = [
    ["Library", "ScriptAssemblies", "Assembly-CSharp.dll"],
    ["Library", "ScriptAssemblies", "Assembly-CSharp-Editor.dll"]
]

class BuildUnitySolutionPhase(BuildSolutionPhase):
    """
    Build phase to build a single solution.
    """

    def init(self, _settings, **kwargs):
        """
        Initialize the build phase, providing basic data.

        @param **kwargs The configuration to initialize the phase
        """
        super(BuildUnitySolutionPhase, self).init(_settings, **kwargs)

    def parse_project(self, project):
        # Parse the base project first
        super(BuildUnitySolutionPhase, self).parse_project(project)

        # Add the Unity3D script assemblies from their final location
        project_dir = os.path.dirname(project)
        for dll in unity_dll_locations:
            opath = os.path.join(project_dir, *dll).replace(os.path.sep, "/")
            if(os.path.isfile(opath)):
                self.add_assembly(opath)

    def __repr__(self):
        return "Unity3D solution phase: '%s' solution: '%s' configs: '%s' valid: '%s'" % (self.name, self._solution, self.configurations, self._is_valid)
