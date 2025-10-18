from PySide6.QtCore import QThread, Signal
import traceback

class Worker(QThread):
    finished = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            import json
            if isinstance(result, (list, dict)):
                self.finished.emit(json.dumps(result))
            else:
                self.finished.emit(str(result) if result is not None else "Task completed successfully.")
        except Exception as e:
            error_msg = f"Task failed: {e}\n\n{traceback.format_exc()}"
            self.finished.emit(error_msg)