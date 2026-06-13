"""Adapters convert a portfolio backend into a flat list of Project records."""

from drift_agent.adapters.base import PortfolioAdapter
from drift_agent.adapters.beacon import BeaconAdapter
from drift_agent.adapters.file import FileAdapter

__all__ = ["PortfolioAdapter", "BeaconAdapter", "FileAdapter"]
