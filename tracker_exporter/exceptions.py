class TrackerExporterError(Exception):
    pass


class ClickhouseError(TrackerExporterError):
    pass


class TrackerError(TrackerExporterError):
    pass


class ExportOrTransformError(TrackerExporterError):
    pass


class UploadError(TrackerExporterError):
    pass


class ConfigurationError(Exception):
    pass


class JsonFileNotFound(Exception):
    pass


class InvalidJsonFormat(Exception):
    pass
