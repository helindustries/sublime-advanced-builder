# Advanced Build System
### for [Sublime Text 2](http://www.sublimetext.com/2)

## About
This Sublime Text 2 package adds advanced building capabilities (advanced as in a little more flexible).

###Features:
* Multiple build phases in a single build system
* Build configuration support to enable or disable certain phases
* Build task support to enable or disable certain phases per task
* Jump to line support for error output.
* Command preconfiguration for multiple projects.
* Per command regular expressions for errors, warnings and messages without order dependancy
* 5 preconfigured types of phases
  - 'command' to run a command
  - 'copy' to copy files around
  - 'solution' to perform a build using a .sln file. This will also add any references and output DLLs from
    the solution to the "completesharp_assemblies" setting of your project (or rather it works for me)
  - 'unity' to build Unity3D solutions. This is the same as a regular solution, but with fixes for assembly references
  - 'stylecop' to check code against StyleCop rules (StyleCop.exe included, linked against Mono)

## Usage
Once installed, you will need to configure the necessary commands in the AdvancedBuilder.sublime-settings file,
contained in this package. If you are on a Mac and using [Unity 3D](http://unity3d.com), then you may find some
commands already work for you. Otherwise, they will provide an example for your own configuration.

Next, you will have to create build phases in your project file. The package comes with some handy completion
snippets, all starting with 'advb_'. Here is an example of how the build phase setup may look:
```
{
    "folders": [
        // ... Your project folders
    ],
    "settings": {
        "advanced_build_phases": [
            {
                "name": "StyleCop rules",                        // Displayed in the output
                "type": "stylecop",                              // The type of build phase
                "tasks": ["Build", "Run"],                       // Include this phase when building or running.
                "configurations": ["Release", "Debug"],          // Include this phase for Debug and Release configurations
                "path": "${project_path}",                       // The path, that should be scanned for C# source files
                "settings": "${project_path}/Settings.StyleCop", // The path to the settings
                "stop_on_error": false,                          // Whether to stop building, if errors are found
                "skip_filters": ["AssemblyInfo.cs$"]             // Don't include these files
                // ... For additional options, please see common/BuildPhase.py and build_phases/StyleCopPhase.py
            },
            {
                "name": "Common build",                // Displayed in the output
                "type": "solution",                    // Build a solution file
                "tasks": ["Build", "Run"],             // Include this phase when building or running.
                "solution": "${folder}/MySolution.sln" // The path to the file
                // ... For additional options, please see common/BuildPhase.py and build_phases/BuildSolutionPhase.py
            },
            {
                "name": "By your command",              // Displayed in the output
                "type": "command",                      // Run a command
                "tasks": ["Build", "Run"],              // Include this phase when building or running.
                "configurations": ["Release", "Debug"], // The configurations, this applies to
                "path_selector": "${project_path}",     // Run this phase only, from files in this path
                "command": [ "mono", "MyProgram" ],     // The command to run
                "stop_on_error": false                  // Stop building, if an error occurs in this phase
                // ... For additional options, please see common/BuildPhase.py and build_phases/RunCommandPhase.py
            }
            {
                "name": "Copy files",                     // Displayed in the output
                "type": "copy",                           // Run a command
                "tasks": ["Build", "Run"],                // Include this phase when building or running.
                "configurations": ["Release"],            // The configurations, this applies to
                "path_selector": "${project_path}",       // Run this phase only, from files in this path
                "destination": "${project_path}/Release", // The destination, files are copied to
                "sources": [                              // The source files, supporting shell wildcards
                    "${project_path}/*.exe",
                    "${project_path}/*.dll"
                ],
                "stop_on_error": false                   // Stop building, if an error occurs in this phase
            }
        ]
    }
}
```
Now select the Advanced Builder [Debug] or Advanced Builder [Release] build system, depending
on the configuration you want to use and start the build. If something goes wrong, please check
the console as it will probably log an exception.

## Install
Get it from [github](https://github.com/ranthor/sublime-advanced-builder/), as there is no integration into
[Package Control](http://wbond.net/sublime\_packages/package\_control) and I don't have any intention of adding
it there any time soon, as this code is not tested nearly enough to warrant a wide-scale release.

## Unknown issues
This thing has been tested by not even a handful of people, exclusively using Mac OS X as their development
platform of choice. So there will be a lot of issues still hidden away, especially in regards to Windows or
Linux as a development platform. If you have problems with this plugin or think it could use some improvements,
please contact me via GitHub. No promises though.

## Known issues
Too many.

* This plugin currently does not work in Sublime Text 3. I may add support later, but at the moment, I am just stuck
  on some issues. I already looked into it, but hit a brick wall because of a lockup when sending lots of data to the
  output view. I may provide a compatible version in the future, but no promises.
* Comments in the project settings will result in an exception from the JSON parser, integrated into python. It is used
  when updating the DLL references for CompleteSharp. There is currently no flag to disable it, sorry.
* The included StyleCop runner will always use all default rules. Even though specifying a valid settings file is
  required for the phase and the StyleCop executable, it does not currently use it for the source code analysis.
* Builds depending on ${project_path} may fail, because the plugin is not able to resolve
  the location of your project file correctly. This happens, when the file is more than 4 steps away from any
  configured folder. It may also take a long time for the plugin to resolve that path, if there are a lot of
  folders configured.
* People, working with JSON may be annoyed by the new build-system and build-phase snippets, just remove them from the
  package directory, should that be the case.

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
