import argparse
import re
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
                          required=True,
                          help="Interval to pull job data from nodes. Do not choose times > 20 seconds!")
config_group.add_argument('--all',
                          action="store_true",
                          dest="run_all",
                          help="Run all available option combinations for sender")

# ---- GENERAL ----
parser.add_argument('--list_versions',
                    help="Lists all available Logger Versions",
                    action="store_true")
parser.add_argument('--list_options',
                    help="Lists all available Options for sepcific Logger Version",
                    dest="logger_version_option")
parser.add_argument('-r', '--reset',
                    help="Reset all devices specified in given config file",
                    dest="reset_config_file")

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
            
    if args.reset_config_file:
        if not os.path.isfile(args.reset_config_file):
            parser_run.exit(message=f"\n\033[1;31mConfig File not found!\033[0m")
        run_uuid = uuid4()
        file = open(args.reset_config_file, "r")
        # ---- PARSE CONFIG FILE ----
        for line in file:
            try:
                nodes.append(SimpleNode(line, run_uuid))
            except IndexError:
                file.close()
                parser_run.exit(message=f"\n\033[1;31mConfig File is malformed!\033[0m")
        file.close()
        
        for node in nodes:
            node.stop_test(collect_data=False)
            
    # ---- PROCESSING ---- RUN ----
    if hasattr(args, "config_file"):
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
        
        if args.run_all:
            for node in nodes:
                node.ping()
                
            receiver = [node for node in nodes if node.type == "receiver"][0]
            receiver.flash()
            
            for node in [_node for _node in nodes if _node.type != "receiver"]:
                available_releases = helper.get_suitable_releases_with_asset_regex("sender-.*\.bin")
                available_logger_versions = [version["name"] for version in available_releases]
                if node.version in available_logger_versions:
                    available_options = helper.get_available_options(node.version, available_releases)
                    for option_combination in [available_option for available_option in available_options if re.search("sender-.*\.bin", available_option["asset"]["name"]) != None]:     
                        node.protocol = option_combination["options"][0]              
                        node.sleep_mode = option_combination["options"][1]
                        node.power_save_mode = option_combination["options"][2]
                        node.flash()
                        
                        receiver.start_test()
                        node.start_test()
                        
                        loops: int = args.duration // args.interval # Floor Division
                        for i in range(loops):
                            time.sleep(args.interval)
                            helper.print_colored(f"Getting Data {i+1}/{loops}", helper.Color.YELLOW)
                            for node in nodes:
                                node.get_data()
                        
                        for node in nodes:
                            node.stop_test()
                else:
                    helper.print_available_versions()
        else:
            # --- TEST ----
            for node in nodes:
                node.ping()
            for node in nodes:
                node.flash()
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