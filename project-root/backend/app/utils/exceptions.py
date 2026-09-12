"""Custom exceptions and a consistent error envelope for the API."""


class AppError(Exception):
    """Base application error. Carries an HTTP status code and machine-readable code."""

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class UnsupportedFileTypeError(AppError):
    status_code = 400
    code = "UNSUPPORTED_FILE_TYPE"


class EmptyFileError(AppError):
    status_code = 400
    code = "EMPTY_FILE"


class CorruptedFileError(AppError):
    status_code = 400
    code = "CORRUPTED_FILE"


class PageLimitExceededError(AppError):
    status_code = 400
    code = "PAGE_LIMIT_EXCEEDED"


class OCRFailureError(AppError):
    status_code = 502
    code = "OCR_FAILURE"


class ExtractionFailureError(AppError):
    status_code = 502
    code = "EXTRACTION_FAILURE"


class DocumentNotFoundError(AppError):
    status_code = 404
    code = "DOCUMENT_NOT_FOUND"


class DatabaseError(AppError):
    status_code = 500
    code = "DATABASE_ERROR"
