'''Instantiate the classes that add buttons to the ribbon'''
from .hybridPostButton import HybridPostButton
from .clonedCommands import ClonedCommands
from .autoSetupButton import AutoSetupButton

commands = [
    ClonedCommands(),
    AutoSetupButton(),
    HybridPostButton()
]


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()
