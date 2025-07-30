import importlib

from .base import BaseClient


client_map = {
    "behavioral": ("behavioralsignals.behavioral", "Behavioral"),
    "deepfakes": ("behavioralsignals.deepfakes", "Deepfakes"),
}


class Client(BaseClient):
    def __getattr__(self, name):
        if name in client_map:
            module_path, class_name = client_map[name]
            module = importlib.import_module(module_path)
            client_class = getattr(module, class_name)
            instance = client_class(cid=self.config.cid, api_key=self.config.api_key)
            setattr(self, name, instance)
            return instance

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
