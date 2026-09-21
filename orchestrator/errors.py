"""Pipeline control-flow exceptions."""


class PipelineError(Exception):
    """Base class."""


class GateBlocked(PipelineError):
    """A blocking gate failed. The run halts and reports why; it never continues."""


class AwaitingInput(PipelineError):
    """The run needs files only a human can supply. Supply them and run again to resume."""


class StageError(PipelineError):
    """A seat returned output the orchestrator cannot use."""


class AlreadyRunning(PipelineError):
    """A run for this brand is already in progress."""
