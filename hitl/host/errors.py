class PreconditionError(RuntimeError):
    exit_code = 2


class OperationError(RuntimeError):
    exit_code = 3
