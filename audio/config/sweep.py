from __future__ import annotations

import pathlib
from typing import Any, Dict

from audio.config.nidaq import NiDaqConfig
from audio.config.plot import PlotConfig

from audio.config.rigol import RigolConfig
from audio.config.sampling import SamplingConfig
from audio.type import Dictionary, Option
from enum import Enum, auto, unique


@unique
class SweepConfigEnum(Enum):
    RIGOL = auto()
    NI_DAQ = auto()
    SAMPLING = auto()
    PLOT = auto()


class SweepConfig(Dictionary):
    def __rich_repr__(self):
        yield "rigol", self.rigol
        yield "nidaq", self.nidaq
        yield "sampling", self.sampling
        yield "plot", self.plot

    @classmethod
    def from_file(
        cls,
        config_file_path: pathlib.Path,
    ) -> Option[SweepConfig]:

        data = Dictionary.from_json(config_file_path)

        if not data.is_null:
            return Option[SweepConfig](cls(data.value))

        return Option[SweepConfig].null()

    def exists(self, config: SweepConfigEnum) -> bool:
        match config:
            case SweepConfigEnum.RIGOL:
                return not self.rigol.is_null
            case SweepConfigEnum.NI_DAQ:
                return not self.nidaq.is_null
            case SweepConfigEnum.SAMPLING:
                return not self.sampling.is_null
            case SweepConfigEnum.PLOT:
                return not self.plot.is_null

    @property
    def rigol(self) -> Option[RigolConfig]:
        return self.get_property("rigol", RigolConfig)

    @property
    def nidaq(self) -> Option[NiDaqConfig]:
        return self.get_property("nidaq", NiDaqConfig)

    @property
    def sampling(self) -> Option[SamplingConfig]:
        return self.get_property("sampling", SamplingConfig)

    @property
    def plot(self) -> Option[PlotConfig]:
        return self.get_property("plot", PlotConfig)

    def set_rigol(
        self,
        override: bool = False,
    ) -> Option[RigolConfig]:
        if self.exists(SweepConfigEnum.RIGOL) or override:
            self.get_dict()["rigol"] = {}
        return self.rigol

    def set_nidaq(
        self,
        override: bool = False,
    ) -> Option[NiDaqConfig]:
        if self.exists(SweepConfigEnum.NI_DAQ) or override:
            self.get_dict()["nidaq"] = {}
        return self.nidaq

    def set_sampling(
        self,
        override: bool = False,
    ) -> Option[SamplingConfig]:
        if self.exists(SweepConfigEnum.SAMPLING) or override:
            self.get_dict()["sampling"] = {}
        return self.sampling

    def set_plot(
        self,
        override: bool = False,
    ) -> Option[PlotConfig]:
        if self.exists(SweepConfigEnum.PLOT) or override:
            self.get_dict()["plot"] = {}
        return self.plot
