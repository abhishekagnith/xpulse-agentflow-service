import logging
from logging_loki import LokiHandler
from dotenv import load_dotenv
import os

class NonEmptyTagsFilter(logging.Filter):
    def filter(self, record):
        # Check if the record has 'tags' attribute
        tags = getattr(record, 'tags', None)
        if tags is None:
            return True  # No tags to check, allow the record
        # Exclude the record if any tag value is empty or None
        for key, value in tags.items():
            if value is None or value == '':
                return False
        return True

class LogUtil:
    def __init__(self):

        # Load environment variables
        load_dotenv()

        # Initialize Loki handler
        self.handler = LokiHandler(
            url=os.getenv("LOKI_URL", "http://143.244.131.181:3100/loki/api/v1/push"),
            tags={"application": "xpulse_flow_service", "environment": os.getenv("APP_ENV", "production"), "org_id": os.getenv("ORG_ID", "AgentCord")},
            version="1"
        )
        self.handler.addFilter(NonEmptyTagsFilter())
        self.logger = logging.getLogger("xpulse_flow_service")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        
        # Add console handler for local terminal output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Suppress pymongo background task errors (set to WARNING to reduce noise)
        pymongo_logger = logging.getLogger("pymongo")
        pymongo_logger.setLevel(logging.WARNING)  # Suppress INFO and DEBUG messages from pymongo
        
        # Suppress motor (async pymongo) background task errors
        motor_logger = logging.getLogger("motor")
        motor_logger.setLevel(logging.WARNING)  # Suppress INFO and DEBUG messages from motor

    def info(self, service_name: str, message: str):
        self.logger.info(f"{message}", extra={"tags": {"service_name": service_name}})

    def error(self, service_name: str, message: str):
        self.logger.error(f"{message}", extra={"tags": {"service_name": service_name}})

    def warning(self, service_name: str, message: str):
        self.logger.warning(f"{message}", extra={"tags": {"service_name": service_name}})

    def debug(self, service_name: str, message: str):
        self.logger.debug(f"{message}", extra={"tags": {"service_name": service_name}})

