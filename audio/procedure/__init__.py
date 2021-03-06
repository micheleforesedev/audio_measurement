from __future__ import annotations
from asyncio import set_event_loop_policy
from calendar import c
import pathlib
from typing import Dict, List, Optional
from weakref import ProxyType
from pytest import console_main

import rich
from tomlkit import value

from audio.config import Config_Dict
from audio.config.sweep import SweepConfig, SweepConfigXML
from audio.console import console
from audio.type import Dictionary, Option

import xml.etree.ElementTree as ET


class ProcedureStep:
    pass


@rich.repr.auto
class ProcedureText(ProcedureStep):
    text: str

    def __init__(self, text: str) -> None:
        self.text = text

    @classmethod
    def from_dict(cls, data: Dictionary):

        text = data.get_property("text", str)
        if text is not None:
            return cls(text)
        else:
            return None


@rich.repr.auto
class ProcedureSetLevel(ProcedureStep):
    name: str
    config: SweepConfigXML

    def __init__(self, name: str, config: SweepConfigXML) -> None:
        self.name = name
        self.config = config

    @classmethod
    def from_dict(cls, data: Dictionary):

        name = data.get_property("name", str)
        config = data.get_property("config")

        if config is None:
            raise Exception("config is NULL")

        config = Dictionary(dict(config))

        config = SweepConfigXML.from_dict(config)

        if name is not None and config is not None:
            return cls(name, config)
        else:
            return None


@rich.repr.auto
class ProcedureSweep(ProcedureStep):
    name: str
    set_level: str
    y_offset_dB: str
    name_plot: str
    config: SweepConfigXML

    def __init__(
        self,
        name: str,
        set_level: str,
        y_offset_dB: str,
        name_plot: str,
        config: SweepConfigXML,
    ) -> None:
        self.name = name
        self.set_level = set_level
        self.y_offset_dB = y_offset_dB
        self.name_plot = name_plot
        self.config = config

    @classmethod
    def from_dict(cls, data: Dictionary):

        name = data.get_property("name", str)
        set_level = data.get_property("set_level", str)
        y_offset_dB = data.get_property("y_offset_dB", str)
        name_plot = data.get_property("name_plot", str)
        config = data.get_property("config", Dict)

        if config is None:
            raise Exception("config is NULL")

        config = Dictionary(dict(config))

        config = SweepConfigXML.from_dict(config)

        if (
            name is not None
            and config is not None
            and set_level is not None
            and y_offset_dB is not None
            and name_plot is not None
        ):
            return cls(name, set_level, y_offset_dB, name_plot, config)
        else:
            return None


@rich.repr.auto
class ProcedureSerialNumber(ProcedureStep):

    text: str

    def __init__(self, text: str) -> None:
        self.text = text

    @classmethod
    def from_dict(cls, data: Dictionary):

        text = data.get_property("text", str)

        if text is not None:
            return cls(text)
        else:
            return None


@rich.repr.auto
class ProcedureInsertionGain(ProcedureStep):

    name: str
    set_level: str

    def __init__(self, name: str, set_level: str) -> None:
        self.name = name
        self.set_level = set_level

    @classmethod
    def from_dict(cls, data: Dictionary):

        name = data.get_property("name", str)
        set_level = data.get_property("set_level", str)

        if name is not None and set_level is not None:
            return cls(name, set_level)
        else:
            return None


@rich.repr.auto
class ProcedurePrint(ProcedureStep):

    variables: List[str] = []

    def __init__(self, variables: List[str]) -> None:
        self.variables = variables

    @classmethod
    def from_dict(cls, data: Dictionary):

        variables = data.get_property("variables", List[str])

        if variables is not None:
            return cls(variables)
        else:
            return None


@rich.repr.auto
class Procedure:

    name: str
    steps: List[ProcedureStep]

    def __init__(self, procedure_name: str, steps: List[ProcedureStep]) -> None:
        self.name = procedure_name
        self.steps = steps

    @classmethod
    def from_json(cls, procedure_path: pathlib.Path):
        data: Optional[Dictionary] = Dictionary.from_json(procedure_path)

        if data is not None:
            procedure = ET.Element("procedure")

            name = ET.SubElement(procedure, "name")
            steps = ET.SubElement(procedure, "steps")

            procedure_data = data.get_property("procedure")
            procedure_data = Dictionary(procedure_data)

            if procedure_data is None:
                raise Exception("procedure_data is NULL")

            procedure_name = procedure_data.get_property("name", str)
            procedure_steps = procedure_data.get_property("steps", List[Dictionary])

            name.text = procedure_name

            steps: List[ProcedureStep] = []

            console.print("------------------------------------")

            if procedure_steps is None:
                raise Exception("procedure_steps is NULL")

            console.print(procedure_steps)

            for idx, step in enumerate(procedure_steps):

                step = Dictionary(step)

                procedure_type: Optional[str] = step.get_property("type", str)
                step_dictionary: Optional[Dict] = step.get_property("step", Dict)

                if procedure_type is None:
                    raise Exception(f"procedure_type is NULL at idx: {idx}")

                if step_dictionary is None:
                    raise Exception(f"step_dictionary is NULL at idx: {idx}")

                step_dictionary = Dictionary(step_dictionary)

                procedure: Optional[ProcedureStep] = None

                if procedure_type == "text":
                    procedure = ProcedureText.from_dict(step_dictionary)
                elif procedure_type == "set-level":
                    procedure = ProcedureSetLevel.from_dict(step_dictionary)
                elif procedure_type == "sweep":
                    procedure = ProcedureSweep.from_dict(step_dictionary)
                elif procedure_type == "serial-number":
                    procedure = ProcedureSerialNumber.from_dict(step_dictionary)
                elif procedure_type == "insertion-gain":
                    procedure = ProcedureInsertionGain.from_dict(step_dictionary)
                elif procedure_type == "print":
                    procedure = ProcedurePrint.from_dict(step_dictionary)
                else:
                    procedure = ProcedureStep()

                if procedure is not None:
                    steps.append(procedure)
                else:
                    raise Exception

            return cls(procedure_name, steps)
        else:
            return None
