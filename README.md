# Advanced Build System
### for [Sublime Text 2](http://www.sublimetext.com/2)

## About
This Sublime Text 2 package adds advanced building capabilities (advanced as in a little more flexible).

###Features:
* Multiple build phases in a single build system
* Build configuration support to enable or disable certain phases
* Jump to line support for error output.
* Command preconfiguration
* Per command regular expressions without order dependancy
* Probably maybe mostly platform independant
* 4 preconfigured types of phases
  - 'command' to run a command
  - 'copy' to copy files around
  - 'solution' to perform a build using a .sln file (because I have to work with this sh**). This wil
    also add any references and output DLLs from the solution to the "completesharp_assemblies" setting
    of your project (or rather it works for me)
  - 'stylecop' to check code against StyleCop rules (StyleCop.exe included, linked against Mono)

## Usage
Once installed, you will need to configure the necessary commands in the AdvancedBuilder.sublime-settings file,
contained in this package. If you are on a Mac and using [Unity 3D](http://unity3d.com), then you may find some
commands already work for you. Otherwise, they will provide an example for your own configuration.

Next, you will have to create build systems and a settings overwrite for build phases in your project file.
Your project file should look something like this:
```
{
    "folders": [
        // ... Your project folders
    ],
    "build_systems": [
        {
            "name": "Build Solution [Debug]" // The name, displayed in the build system selection
            "configuration": "Debug",        // The configuration to use, this enables or disables phases
            "target": "advanced_builder",    // This build system definition uses Advanced Build System
            "quiet": true,                   // This will only display errors and phase changes
            "task": "Build"                  // Build or Clean, Build is the default, if nothing is specified
        }
        // ... Additional build systems for additional configurations
    ],
    "settings": {
        "advanced_build_phases": [
            {
                "name": "StyleCop rules",                        // Displayed in the output
                "type": "stylecop",                              // The type of build phase
                "configurations": ["Release", "Debug"]           // Include this phase for Debug and Release configurations
                "path": "${project_path}",                       // The path, that should be scanned for C# source files
                "settings": "${project_path}/Settings.StyleCop", // The path to the settings
                "stop_on_error": false,                          // Whether to stop building, if errors are found
                "skip_filters": ["AssemblyInfo.cs$"],            // Don't include these files
                // ... For additional options, please see common/BuildPhase.py and build_phases/StyleCopPhase.py
            },
            {
                "name": "Common build",                // Displayed in the output
                "type": "solution",                    // Build a solution file
                "solution": "${folder}/MySolution.sln" // The path to the file
                // ... For additional options, please see common/BuildPhase.py and build_phases/BuildSolutionPhase.py
            },
        		{
        			  "name": "By your command",               // Displayed in the output
        			  "type": "command",                       // Run a command
      				  "configurations": ["Release", "Debug"],  // The configurations, this applies to
        			  "path_selector": "${project_path}",      // Run this phase only, from files in this path
      				  "command": [ "echo", "'Hello World!'" ], // The command to run
      				  "stop_on_error": false                   // Stop building, if an error occurs in this phase
                // ... For additional options, please see common/BuildPhase.py and build_phases/RunCommandPhase.py
      			}
            // Copy files phases can be here too, but they are untested!
            // ... Additional build phases, these can be mixed and matched as you like
        ]
    }
}
```
Now select a newly configured build system and start the build. If something goes wrong, please check the console
as it will probably log an exception.

## Install
Get it from [github](https://github.com/ranthor/sublime-advanced-builder/), as there is no integration into
[Package Control](http://wbond.net/sublime\_packages/package\_control). I may do that later, but for the moment,
I only provide this in case someone finds it useful.

If you have problems with this plugin or think it could use some improvements, contact me via GitHub. No promises though.

## Known issues
Too many. For example, builds depending on ${project_path} may fail, because the plugin is not able to resolve
the location of your project file correctly. This happens, when the file is more than 4 steps away from any
configured folder. It may also take a long time for the plugin to resolve that path, if there are a lot of
folders configured.

## License
Copyright (c) 2013, Paul Schulze

All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
OF SUCH DAMAGE.

# Derived Work
This software includes compiled versions of [StyleCop](http://stylecop.codeplex.com/),
governed by its own license (see stylecop/License.rtf) and
[StyleCop-Cmd](http://www.nichesoftware.co.nz/software/stylecop-cmd),
licensed under the MIT license. For task execution, it builds upon the Sublime Text
exec.py command executor, found in the <package_directory>/Default/exec.py.