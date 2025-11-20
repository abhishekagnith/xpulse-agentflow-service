class FlowException(Exception):
    """
    This is the base exception for all flow exceptions
    """
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message, self.status_code)

class FlowDBException(FlowException):
    """
    This is the exception for all flow database exceptions
    """
    def __init__(self, message: str):
        self.message = message
        self.status_code = 500
        super().__init__(message=self.message, status_code=self.status_code)

class FlowServiceException(FlowException):
    """
    This is the exception for all flow service exceptions
    """
    def __init__(self, message: str):
        self.message = message
        self.status_code = 500
        super().__init__(message=self.message, status_code=self.status_code)

class FlowNotFoundException(FlowException):
    """
    This is the exception when flow is not found
    """
    def __init__(self, message: str):
        self.message = message
        self.status_code = 404
        super().__init__(message=self.message, status_code=self.status_code)

class FlowValidationException(FlowException):
    """
    This is the exception for flow validation errors
    """
    def __init__(self, message: str):
        self.message = message
        self.status_code = 400
        super().__init__(message=self.message, status_code=self.status_code)

