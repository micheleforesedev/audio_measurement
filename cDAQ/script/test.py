import click
from cDAQ.timer import timeit
from cDAQ.console import console
from cDAQ.usbtmc import UsbTmc


def say_hi():
    console.print("HI!!")


@click.command(help="Test for Timer class")
def testTimer():

    decorator = timeit()
    timed_say_hi = decorator(say_hi)

    timed_say_hi()

    timeit()(say_hi)()


@click.command()
def print_devices():

    list = UsbTmc.search_devices()

    instr = list[-1]
    print(instr.ask("*IDN?"))

    console.print(list)
