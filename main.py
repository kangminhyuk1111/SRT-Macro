import sys
import os

if getattr(sys, "frozen", False):
    from src.config.settings import _frozen_base
    os.chdir(_frozen_base())
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.gui.launcher import choose_rail, make_manager
from src.gui.app import App

if __name__ == "__main__":
    rail = choose_rail()
    if rail:
        app = App(make_manager(rail))
        app.run()
