import argparse
import textwrap
import time
import os
from uuid import uuid4

import helper
from simple_node import SimpleNode

parser = argparse.ArgumentParser(prog="Sensor Network Testsuit",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description=textwrap.dedent('''\
                                    Provides easy operations to test a sensor network.
                                    Developed by Philipp Tebbe - 2024
                                    '''),
                                 epilog="For more information visit: https://github.com/phsete/PPK2forESP")

subparsers = parser.add_subparsers(help='available operations')
parser_run = subparsers.add_parser('run', help='run a test')

# ---- RUN ----
# logging_group = parser_run.add_argument_group('Logging')
# logging_group.add_argument('-so', '--sender_output',
#                     required=False,
#                     dest="sender_output_file")
# logging_group.add_argument('-ro', '--receiver_output',
#                     required=False,
#                     dest="receiver_output_file")

config_group = parser_run.add_argument_group('Configuration')
config_group.add_argument('-c', '--config',
                          default="nodes.save",
                          dest="config_file")
config_group.add_argument('-t', '--duration',
                          dest="duration",
                          type=int,
                          required=True)
config_group.add_argument('-i', '--interval',
                          dest="interval",
                          type=int,
                          required=True)

# ---- GENERAL ----
parser.add_argument('--list_versions',
                    help="Lists all available Logger Versions",
                    action="store_true")
parser.add_argument('--list_options',
                    help="Lists all available Options for sepcific Logger Version",
                    dest="logger_version_option")

args = parser.parse_args()

nodes: list[SimpleNode] = []

def main():
    # ---- PROCESSING ---- GENERAL ----
    if args.list_versions:
        helper.print_available_versions()
            
    if args.logger_version_option:
        version_found = helper.print_available_options(args.logger_version_option)
        if not version_found:
            parser_run.exit(message=f"\n\033[1;31mSpecified Version not found!\033[0m")
            
    # ---- PROCESSING ---- RUN ----
    if args.config_file:
        if not os.path.isfile(args.config_file):
            parser_run.exit(message=f"\n\033[1;31mConfig File not found!\033[0m")
        run_uuid = uuid4()
        file = open(args.config_file, "r")
        # ---- PARSE CONFIG FILE ----
        for line in file:
            try:
                nodes.append(SimpleNode(line, run_uuid))
            except IndexError:
                file.close()
                parser_run.exit(message=f"\n\033[1;31mConfig File is malformed!\033[0m")
        file.close()
        
        # --- TEST ----
        for node in nodes:
            node.ping()
        for node in nodes:
            node.start_test()
        
        loops: int = args.duration // args.interval # Floor Division
        for i in range(loops):
            time.sleep(args.interval)
            helper.print_colored(f"Getting Data {i+1}/{loops}", helper.Color.YELLOW)
            for node in nodes:
                node.get_data()
        
        for node in nodes:
            node.stop_test()
        
if __name__ == '__main__':
    main()