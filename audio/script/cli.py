import pathlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from rich.panel import Panel
from rich.prompt import Confirm

from audio.config.sweep import SweepConfig
from audio.config.type import Range
from audio.console import console
from audio.docker.latex import create_latex_file
from audio.math import find_sin_zero_offset, rms_full_cycle
from audio.math.interpolation import INTERPOLATION_KIND, interpolation_model
from audio.math.rms import RMS
from audio.model.sweep import SingleSweepData
from audio.sampling import config_set_level, plot_from_csv, sampling_curve
from audio.script.device.ni import read_rms
from audio.script.device.rigol import set_amplitude, set_frequency, turn_off, turn_on
from audio.script.procedure import procedure
from audio.script.test import print_devices, testTimer
from audio.utility import get_subfolder
from audio.utility.timer import Timer


@click.group()
def cli():
    """This is the CLI for the audio measurements tools"""
    pass


@cli.command(help="Audio Sweep")
@click.option(
    "--config",
    "config_path",
    type=pathlib.Path,
    help="Configuration path of the config file in json5 format.",
    required=True,
)
@click.option(
    "--home",
    type=pathlib.Path,
    help="Home path, where the csv and plot image will be created.",
    default=pathlib.Path.cwd(),
    show_default=True,
)
@click.option(
    "--set_level_file",
    "set_level_file",
    type=pathlib.Path,
    help="Set Level file path.",
    default=None,
)
# Config Overloads
@click.option(
    "--amplitude_pp",
    type=float,
    help="The Amplitude of generated wave.",
    default=None,
)
@click.option(
    "--n_fs",
    type=float,
    help="Fs * n. Oversampling.",
    default=None,
)
@click.option(
    "--spd",
    type=float,
    help="Samples per decade.",
    default=None,
)
@click.option(
    "--n_samp",
    type=int,
    help="Number of samples.",
    default=None,
)
@click.option(
    "--f_range",
    nargs=2,
    type=(float, float),
    help="Samples Frequency Range.",
    default=None,
)
@click.option(
    "--y_lim",
    nargs=2,
    type=(float, float),
    help="Range y Plot.",
    default=None,
)
@click.option(
    "--x_lim",
    nargs=2,
    type=(float, float),
    help="Range x Plot.",
    default=None,
)
@click.option(
    "--y_offset",
    type=float,
    help="Offset value.",
    default=None,
)
# Flags
@click.option(
    "--time/--no-time",
    help="Show elapsed time.",
    default=False,
)
@click.option(
    "--debug/--no-debug",
    "debug",
    help="Will print verbose messages.",
    default=False,
)
@click.option(
    "--simulate",
    is_flag=True,
    help="Will Simulate the Sweep.",
    default=False,
)
@click.option(
    "--pdf/--no-pdf",
    "pdf",
    help="Will skip the pdf creation.",
    default=True,
)
def sweep(
    config_path: pathlib.Path,
    home: pathlib.Path,
    set_level_file: Optional[pathlib.Path],
    amplitude_pp: Optional[float],
    n_fs: Optional[float],
    spd: Optional[float],
    n_samp: Optional[int],
    f_range: Optional[Tuple[float, float]],
    y_lim: Optional[Tuple[float, float]],
    x_lim: Optional[Tuple[float, float]],
    y_offset: Optional[float],
    time: bool,
    debug: bool,
    simulate: bool,
    pdf: bool,
):

    HOME_PATH = home.absolute().resolve()

    datetime_now = datetime.now().strftime(r"%Y-%m-%d--%H-%M-%f")

    # Load JSON config
    config_file = config_path.absolute()
    cfg = SweepConfig.from_file(config_file)

    if debug:
        console.print(cfg)

    # Override Configurations
    cfg.rigol.override(amplitude_pp)

    cfg.sampling.override(
        fs=n_fs,
        points_per_decade=spd,
        number_of_samples=n_samp,
        f_min=f_range[0] if f_range else None,
        f_max=f_range[1] if f_range else None,
    )

    if set_level_file:
        amplitude_base_level = float(set_level_file.read_text())
    else:
        set_level_file_list = [
            set_level_file for set_level_file in HOME_PATH.glob("*.config.offset")
        ]
        if len(set_level_file_list) > 0:
            pattern: str = r"%Y-%m-%d--%H-%M-%f"
            set_level_file_list.sort(
                key=lambda name: datetime.datetime.strptime(
                    name.name.strip(".")[0], pattern
                ),
            )
            amplitude_base_level = float(set_level_file_list[-1].read_text())
        else:
            raise Exception

    cfg.rigol.override(amplitude_pp=amplitude_base_level)

    # TODO: da mettere come parametro (default ?? questo sotto)
    y_offset = 1.227653

    cfg.plot.override(
        y_offset=y_offset,
        x_limit=Range(*x_lim) if x_lim else None,
        y_limit=Range(*y_lim) if y_lim else None,
    )

    if debug:
        console.print(cfg)

    measurements_dir: pathlib.Path = HOME_PATH / f"{datetime_now}"
    measurements_dir.mkdir(parents=True, exist_ok=True)

    measurements_file: pathlib.Path = measurements_dir / "sweep.csv"
    image_file: pathlib.Path = measurements_dir / "sweep.png"

    if not simulate:
        timer = Timer("Sweep time")

        if time:
            timer.start()

        sampling_curve(
            config=cfg,
            measurements_file_path=measurements_file,
            debug=debug,
        )

        if time:
            timer.stop().print()

    if not simulate:

        plot_from_csv(
            measurements_file_path=measurements_file,
            plot_file_path=image_file,
            plot_config=cfg.plot,
            debug=debug,
        )

        if pdf:
            create_latex_file(
                image_file, home=HOME_PATH, latex_home=measurements_dir, debug=debug
            )


@cli.command(help="Plot from a csv file.")
@click.option(
    "--csv",
    type=pathlib.Path,
    help="Measurements file path in csv format.",
    default=None,
)
@click.option(
    "--home",
    type=pathlib.Path,
    help="Home path, where the plot image will be created.",
    default=pathlib.Path.cwd(),
    show_default=True,
)
@click.option(
    "--config",
    "config_path",
    type=pathlib.Path,
    help="Configuration path of the config file in json5 format.",
    default=None,
)
@click.option(
    "--format-plot",
    "format_plot",
    type=click.Choice(["png", "pdf"], case_sensitive=False),
    multiple=True,
    help='Format of the plot, can be: "png" or "pdf".',
    default=["png"],
    show_default=True,
)
@click.option(
    "--y_lim",
    nargs=2,
    type=(float, float),
    help="Range y Plot.",
    default=None,
)
@click.option(
    "--x_lim",
    nargs=2,
    type=(float, float),
    help="Range x Plot.",
    default=None,
)
@click.option(
    "--y_offset",
    type=float,
    help="Offset value.",
    default=None,
)
@click.option(
    "--interpolation_rate",
    "interpolation_rate",
    type=float,
    help="Interpolation Rate.",
    default=None,
)
@click.option(
    "--dpi",
    type=int,
    help="Dpi Resolution for the image.",
    default=None,
)
@click.option(
    "--pdf/--no-pdf",
    "pdf",
    help="Will skip the pdf creation.",
    default=True,
)
@click.option(
    "--debug",
    is_flag=True,
    help="Will print verbose messages.",
    default=False,
)
def plot(
    csv: Optional[pathlib.Path],
    home: pathlib.Path,
    config_path: Optional[pathlib.Path],
    format_plot: List[str],
    y_lim: Optional[Tuple[float, float]],
    x_lim: Optional[Tuple[float, float]],
    y_offset: Optional[float],
    interpolation_rate: Optional[float],
    dpi: Optional[int],
    pdf: bool,
    debug: bool,
):
    HOME_PATH = home.absolute()
    csv_file: pathlib.Path = pathlib.Path()
    plot_file: Optional[pathlib.Path] = None

    sweep_config = SweepConfig.from_file(config_path)
    plot_config: Plot = Plot()

    if sweep_config:
        plot_config = sweep_config.plot

        plot_config.override(
            y_offset=y_offset,
            x_limit=Range(*x_lim) if x_lim else None,
            y_limit=Range(*y_lim) if y_lim else None,
            interpolation_rate=interpolation_rate,
            dpi=dpi,
        )
    else:
        plot_config = plot_config.from_value(
            y_offset=y_offset,
            x_limit=Range(*x_lim) if x_lim else None,
            y_limit=Range(*y_lim) if y_lim else None,
            interpolation_rate=interpolation_rate,
            dpi=dpi,
        )

    console.print(plot_config)

    is_most_recent_file: bool = False
    plot_file: Optional[pathlib.Path] = None

    latex_home: pathlib.Path = pathlib.Path()

    if csv:
        if csv.exists() and csv.is_file():
            latex_home = csv.parent
            csv_file = csv.absolute()
            plot_file = csv_file.with_suffix("")
        else:
            console.print(
                Panel("File: '{}' doesn't exists.".format(csv), style="error")
            )
            is_most_recent_file = Confirm.ask(
                "Do you want to search for the most recent '[italic].csv[/]' file?",
                default=False,
            )
    else:
        is_most_recent_file = True

    if is_most_recent_file:

        measurement_dirs: List[pathlib.Path] = get_subfolder(HOME_PATH)

        if len(measurement_dirs) > 0:
            csv_file = measurement_dirs[-1] / "sweep.csv"

            if csv_file.exists() and csv_file.is_file():
                plot_file = csv_file.with_suffix("")
                latex_home = csv_file.parent
        else:
            console.print("There is no csv file available.", style="error")

    if plot_file:
        for plot_file_format in format_plot:
            plot_file = plot_file.with_suffix("." + plot_file_format)
            console.print(f'Plotting file: "{plot_file.absolute()}"')
            plot_from_csv(
                measurements_file_path=csv_file,
                plot_file_path=plot_file,
                plot_config=plot_config,
                debug=debug,
            )
            if plot_file_format == "png":
                if pdf:
                    create_latex_file(plot_file, home=HOME_PATH, latex_home=latex_home)
    else:
        console.print("Cannot create a plot file.", style="error")


@cli.command(help="Gets the config Offset Through PID Controller.")
@click.option(
    "--config",
    "config_path",
    type=pathlib.Path,
    help="Configuration path of the config file in json5 format.",
    required=True,
)
@click.option(
    "--home",
    type=pathlib.Path,
    help="Home path, where the plot image will be created.",
    default=pathlib.Path.cwd(),
    show_default=True,
)
@click.option(
    "--debug",
    is_flag=True,
    help="Will print verbose messages.",
    default=False,
)
def set_level(
    config_path: pathlib.Path,
    home: pathlib.Path,
    debug: bool,
):
    HOME_PATH = home.absolute().resolve()

    datetime_now = datetime.now().strftime(r"%Y-%m-%d--%H-%M-%f")

    config_file = config_path.absolute()
    config: SweepConfig = SweepConfig.from_file(config_file)

    if debug:
        console.print(config)

    config_set_level(
        config=config.sampling,
        plot_file_path=HOME_PATH / "{}.config.png".format(datetime_now),
        debug=debug,
    )


@cli.command()
@click.option(
    "--home",
    type=pathlib.Path,
    help="Home path, where the plot image will be created.",
    default=pathlib.Path.cwd(),
    show_default=True,
)
@click.option(
    "--sweep-dir",
    "sweep_dir",
    type=pathlib.Path,
    help="Home path, where the plot image will be created.",
    default=None,
)
@click.option(
    "--iteration-rms/--no-iteration-rms",
    "iteration_rms",
    help="Home path, where the plot image will be created.",
    default=False,
)
def sweep_debug(
    home,
    sweep_dir: Optional[pathlib.Path],
    iteration_rms: bool,
):
    measurement_dir: pathlib.Path = pathlib.Path()

    if sweep_dir:
        measurement_dir = sweep_dir / "sweep"

    else:
        measurement_dirs: List[pathlib.Path] = get_subfolder(home)

        if len(measurement_dirs) > 0:
            measurement_dir = measurement_dirs[-1] / "sweep"
        else:
            console.print(
                "Cannot create the debug info from sweep csvs.", style="error"
            )
            exit()

    if not measurement_dir.exists() or not measurement_dir.is_dir():
        console.print("The measurement directory doesn't exists.")
        exit()

    csv_files = [csv for csv in measurement_dir.rglob("sample.csv") if csv.is_file()]

    if len(csv_files) > 0:
        csv_files.sort(key=lambda name: float(name.parent.name.replace("_", ".")))

    for csv in csv_files:
        csv_parent = csv.parent
        plot_image = csv_parent / "plot.png"

        sweep_data = SingleSweepData(csv)

        plot: Tuple[Figure, Dict[str, Axes]] = plt.subplot_mosaic(
            [
                ["samp", "samp", "rms_samp"],
                ["intr_samp", "intr_samp", "rms_intr_samp"],
                ["intr_samp_offset", "intr_samp_offset", "rms_intr_samp_offset"],
                [
                    "rms_intr_samp_offset_trim",
                    "rms_intr_samp_offset_trim",
                    "rms_intr_samp_offset_trim",
                ],
            ],
            figsize=(30, 20),
            dpi=300,
        )
        # plt.tight_layout()

        fig, axd = plot

        for ax_key in axd:
            axd[ax_key].grid(True)

        fig.suptitle(f"Frequency: {sweep_data.frequency} Hz.", fontsize=30)
        fig.subplots_adjust(
            wspace=0.5,  # the amount of width reserved for blank space between subplots
            hspace=0.5,  # the amount of height reserved for white space between subplots
        )

        # PLOT: Samples on Time Domain
        ax_time_domain_samples = axd["samp"]

        rms_samp = RMS.fft(sweep_data.voltages.values)

        ax_time_domain_samples.plot(
            np.linspace(
                0,
                len(sweep_data.voltages) / sweep_data.Fs,
                len(sweep_data.voltages),
            ),
            sweep_data.voltages,
            marker=".",
            markersize=3,
            linestyle="-",
            linewidth=1,
            label=f"Voltage Sample - rms={rms_samp:.5}",
        )
        ax_time_domain_samples.set_title(
            f"Samples on Time Domain - Frequency: {round(sweep_data.frequency, 5)}"
        )
        ax_time_domain_samples.set_ylabel("Voltage [$V$]")
        ax_time_domain_samples.set_xlabel("Time [$s$]")
        # ax_time_domain_samples.legend(bbox_to_anchor=(1, 0.5), loc="center left")
        ax_time_domain_samples.legend(loc="best")

        # PLOT: RMS iterating every 5 values
        if iteration_rms:
            plot_rms_samp = axd["rms_samp"]
            rms_samp_iter_list: List[float] = [0]
            for n in range(5, len(sweep_data.voltages.values), 5):
                rms_samp_iter_list.append(RMS.fft(sweep_data.voltages.values[0:n]))

            plot_rms_samp.plot(
                np.arange(
                    0,
                    len(sweep_data.voltages),
                    5,
                ),
                rms_samp_iter_list,
                label="Iterations Sample RMS",
            )
            plot_rms_samp.legend(loc="best")

        plot_intr_samp = axd["intr_samp"]
        voltages_to_interpolate = sweep_data.voltages.values
        INTERPOLATION_RATE = 10
        x_interpolated, y_interpolated = interpolation_model(
            range(0, len(voltages_to_interpolate)),
            voltages_to_interpolate,
            int(len(voltages_to_interpolate) * INTERPOLATION_RATE),
            kind=INTERPOLATION_KIND.CUBIC,
        )

        pd.DataFrame(y_interpolated).to_csv(
            pathlib.Path(csv_parent / "interpolation_sample.csv").absolute().resolve(),
            header=["voltage"],
            index=None,
        )

        rms_intr = RMS.fft(y_interpolated)
        plot_intr_samp.plot(
            np.linspace(
                0,
                len(y_interpolated) / (sweep_data.Fs * INTERPOLATION_RATE),
                len(y_interpolated),
            ),
            # x_interpolated,
            y_interpolated,
            linestyle="-",
            linewidth=0.5,
            label=f"rms={rms_intr:.5}",
        )
        plot_intr_samp.set_title("Interpolated Samples")
        plot_intr_samp.set_ylabel("Voltage [$V$]")
        plot_intr_samp.set_xlabel("Time [$s$]")
        plot_intr_samp.legend(loc="best")

        if iteration_rms:
            plot_rms_intr_samp = axd["rms_intr_samp"]
            rms_intr_samp_iter_list: List[float] = [0]
            for n in range(1, len(y_interpolated), 20):
                rms_intr_samp_iter_list.append(RMS.fft(y_interpolated[0:n]))

            plot_rms_intr_samp.plot(
                rms_intr_samp_iter_list,
                label="Iterations Interpolated Sample RMS",
            )
            plot_rms_intr_samp.legend(loc="best")

        # PLOT: Interpolated Sample, Zero Offset for complete Cycles
        offset_interpolated, idx_start, idx_end = find_sin_zero_offset(y_interpolated)

        plot_intr_samp_offset = axd["intr_samp_offset"]
        rms_intr_offset = RMS.fft(offset_interpolated)
        plot_intr_samp_offset.plot(
            np.linspace(
                idx_start / sweep_data.Fs,
                len(offset_interpolated) / (sweep_data.Fs * INTERPOLATION_RATE),
                len(offset_interpolated),
            ),
            offset_interpolated,
            linewidth=0.7,
            label=f"rms={rms_intr_offset:.5}",
        )
        plot_intr_samp_offset.set_title("Interpolated Samples with Offset")
        plot_intr_samp_offset.set_ylabel("Voltage [$V$]")
        plot_intr_samp_offset.set_xlabel("Time [$s$]")
        plot_intr_samp_offset.legend(loc="best")

        if iteration_rms:
            plot_rms_intr_samp_offset = axd["rms_intr_samp_offset"]
            rms_intr_samp_offset_iter_list: List[float] = [0]

            for n in range(1, len(offset_interpolated), 20):
                rms_intr_samp_offset_iter_list.append(RMS.fft(offset_interpolated[0:n]))

            pd.DataFrame(rms_intr_samp_offset_iter_list).to_csv(
                pathlib.Path(csv_parent / "interpolation_rms.csv").absolute().resolve(),
                header=["voltage"],
                index=None,
            )

            plot_rms_intr_samp_offset.plot(
                rms_intr_samp_offset_iter_list,
                label="Iterations Interpolated Sample with Offset RMS",
            )
            plot_rms_intr_samp_offset.legend(loc="best")

        # PLOT: RMS every sine period
        plot_rms_intr_samp_offset_trim = axd["rms_intr_samp_offset_trim"]
        (plot_rms_fft_intr_samp_offset_trim_list) = rms_full_cycle(offset_interpolated)

        plot_rms_intr_samp_offset_trim.plot(
            plot_rms_fft_intr_samp_offset_trim_list,
            label="RMS fft per period, Interpolated",
        )
        plot_rms_intr_samp_offset_trim.legend(loc="best")

        plt.savefig(plot_image)
        plt.close("all")

        console.print(f"Plotted Frequency: [blue]{sweep_data.frequency:7.5}[/].")


cli.add_command(procedure)


@cli.group()
def rigol():
    pass


rigol.add_command(turn_on)
rigol.add_command(turn_off)
rigol.add_command(set_frequency)
rigol.add_command(set_amplitude)


@cli.group()
def ni():
    pass


ni.add_command(read_rms)


@cli.group()
def test():
    pass


test.add_command(testTimer)
test.add_command(print_devices)


@test.command()
def config():

    pass
