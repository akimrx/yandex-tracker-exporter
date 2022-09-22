class TrackerExporterError(Exception):
    pass


class ClickhouseError(TrackerExporterError):
    pass


class TrackerError(TrackerExporterError):
    pass


class NetworkError(TrackerExporterError):
    pass


class ExportError(TrackerExporterError):
    pass


class TimedOut(TrackerExporterError):
    def __init__(self):
        super().__init__("Timed out")
