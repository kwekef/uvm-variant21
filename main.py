import argparse

from src.gui.main_gui import start_program
from src.web.app import start
from src.tools.run_tests import main as run_tests_main


def main(mode):
    if mode == "gui":
        start_program()
    elif mode == "web":
        start()
    elif mode == "tests":
        run_tests_main()
    else:
        print("Invalid mode")


if __name__ == "__main__":
    program = argparse.ArgumentParser(description="UVM")
    program.add_argument("-m", "--mode", choices=["gui", "web", "tests"], type=str, default="gui")
    args = program.parse_args()
    main(args.mode)
