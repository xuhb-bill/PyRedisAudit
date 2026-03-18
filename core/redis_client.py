import redis
import logging

class RedisClient:
    """
    A helper class to handle connections to a Redis instance.
    """
    def __init__(self, host='127.0.0.1', port=6379, password=None, db=0):
        self.host = host
        self.port = int(port)
        self.password = password
        self.db = int(db)
        self.client = None
        self.logger = logging.getLogger("RedisClient")

    def connect(self):
        """
        Connect to the Redis instance.
        """
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                socket_timeout=5,
                decode_responses=True
            )
            # Try to ping the server to verify connection
            self.client.ping()
            self.logger.info(f"Connected to Redis at {self.host}:{self.port}")
            return True, "Success"
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to connect to Redis at {self.host}:{self.port}: {error_msg}")
            self.client = None
            return False, error_msg

    def get_server_version(self):
        """
        Fetch the Redis server version.
        """
        if not self.client:
            return None
        try:
            info = self.client.info("server")
            return info.get("redis_version")
        except Exception as e:
            self.logger.error(f"Failed to fetch server info: {e}")
            return None

    def key_exists(self, key):
        """
        Check if a key exists in the current database.
        """
        if not self.client:
            return False
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            self.logger.error(f"Failed to check key existence: {e}")
            return False

    def execute(self, tokens):
        if not self.client:
            return False, 'Redis client not connected'
        if not tokens or not isinstance(tokens, (list, tuple)):
            return False, 'Invalid command tokens'
        try:
            result = self.client.execute_command(*tokens)
            return True, result
        except Exception as e:
            return False, str(e)

    def close(self):
        """
        Close the Redis connection.
        """
        if self.client:
            self.client.close()
            self.client = None
