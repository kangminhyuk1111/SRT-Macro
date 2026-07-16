import sys
import os

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.gui.launcher import choose_rail, make_manager
from src.gui.app import App

if __name__ == "__main__":
    rail = choose_rail()
    if rail:
        app = App(make_manager(rail))
        app.run()
