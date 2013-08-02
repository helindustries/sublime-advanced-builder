__all__ = ["BuildSolutionPhase", "BuildUnitySolutionPhase", "CopyFilesPhase", "StyleCopPhase", "RunCommandPhase"]

import sublime
if int(sublime.version()) < 3000:
    from build_solution_phase import BuildSolutionPhase
    from build_unity_solution_phase import BuildUnitySolutionPhase
    from copy_files_phase import CopyFilesPhase
    from stylecop_phase import StyleCopPhase
    from run_command_phase import RunCommandPhase
else:
    from .build_solution_phase import BuildSolutionPhase
    from .build_unity_solution_phase import BuildUnitySolutionPhase
    from .copy_files_phase import CopyFilesPhase
    from .stylecop_phase import StyleCopPhase
    from .run_command_phase import RunCommandPhase
