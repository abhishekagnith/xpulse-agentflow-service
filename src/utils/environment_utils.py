from dotenv import load_dotenv
import os

# Utils
from utils.log_utils import LogUtil

"""
Utility class for environment variables
"""
class EnvironmentUtils:
    def __init__(self, log_util: LogUtil):

        # Load environment variables
        load_dotenv()

        # Initialize logger
        self.log_util = log_util

        # Environment variables
        self.env_variables = {
            "APP_ENV": os.getenv("APP_ENV", "production"),
            "HOST": os.getenv("HOST", "0.0.0.0"),
            "PORT": int(os.getenv("PORT", "8018")),
            "ORG_ID": os.getenv("ORG_ID", "AgentCord"),
            "LOKI_URL": os.getenv("LOKI_URL", "http://143.244.131.181:3100/loki/api/v1/push"),
            "MONGO_USERNAME": os.getenv("MONGO_USERNAME", "agentflowservice"),
            "MONGO_PASSWORD": os.getenv("MONGO_PASSWORD", "4g3ntfL0wuS3r"),
            "MONGO_AUTH_SOURCE": os.getenv("MONGO_AUTH_SOURCE", "admin"),
            "MONGO_HOST": os.getenv("MONGO_HOST", "157.245.98.53"),
            "MONGO_PORT": int(os.getenv("MONGO_PORT", "27017")),
            "MONGO_DB_NAME": os.getenv("MONGO_DB_NAME", "flow_db"),
            "DEBUG": os.getenv("DEBUG", "false"),
        }

    def get_env_variable(self, variable_name: str) -> str | int:
        if variable_name not in self.env_variables:
            self.log_util.error(service_name="EnvironmentUtils", message=f"Environment variable {variable_name} not found")
            raise ValueError(f"Environment variable {variable_name} not found")
        return self.env_variables[variable_name]

