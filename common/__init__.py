__all__ = ["BuildPhase", "AdvancedBuilderSettings", "printcons"]

import sublime
if int(sublime.version()) < 3000:
    from build_phase import BuildPhase
    from settings import AdvancedBuilderSettings
else:
    from .build_phase import BuildPhase
    from .settings import AdvancedBuilderSettings
