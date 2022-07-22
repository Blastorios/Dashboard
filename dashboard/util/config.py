"""
Reusable Config Component
"""
from dataclasses import dataclass


@dataclass
class Config:
    def __getitem__(self, key):
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)
