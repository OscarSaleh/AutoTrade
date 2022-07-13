# ==================================================================================================================
# Main_Scheduler.py
# ==================================================================================================================
# This program launches programs at specific times.
# ==================================================================================================================
# Date      User         Remarks
# 20211116  Oscar Saleh  Original program.
# 20211214  Oscar Saleh  Implement Exit flag.
# 20211226  Oscar Saleh  Proof of concept accomplished.
#
# ==================================================================================================================
# Pending items:
# - Optimize process (after proof of concept).
#
# ==================================================================================================================
# Objective:
# This program schedules or runs programs at specific times.
#
# ==================================================================================================================
# Logic:
# - The program read schedule and launch processes as needed.
#
# ==================================================================================================================

import configparser
import datetime
import os
import requests
import subprocess
import sys
import time

# from configparser import SafeConfigParser
from datetime import datetime, timedelta
from operator import attrgetter
from shutil import copyfile

def func_run_process(int_time_hours, int_time_minutes, int_runtime_minutes):
    global dt_trading_timestamp

    if (os.path.isfile(str_path_dir_Config + '\Scheduler_Exit.txt')):
        return

    print('waiting for ' + str(int_time_hours) + ':' + str(int_time_minutes) + ' hours-minutes ET.')
    dt_trading_timestamp = datetime.today() + timedelta(minutes=60)
    while (dt_trading_timestamp < dt_trading_timestamp.replace(hour=int_time_hours, minute=int_time_minutes, second=0, microsecond=0)):
        if (os.path.isfile(str_path_dir_Config + '\Scheduler_Exit.txt')):
            return
        time.sleep(60)  # delay time
        dt_trading_timestamp = datetime.today() + timedelta(minutes=60)

    if (os.path.isfile(str_path_dir_Config + '\Scheduler_Exit.txt')):
        return

    print('verify trade process will start.')
    if (os.path.isfile(str_path_dir_Config + '\Trade_Exit.txt')):
        os.rename(str_path_dir_Config + '\Trade_Exit.txt', str_path_dir_Config + '\Trade_ExitNO.txt')
    print('running trade process for ' + str(int_runtime_minutes) + ' minutes.')
    subprocess.Popen(["python.exe", "Main_Trade.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)

    int_counter = 0
    while (int_counter < int_runtime_minutes):
        if (os.path.isfile(str_path_dir_Config + '\Scheduler_Exit.txt')):
            if (os.path.isfile(str_path_dir_Config + '\Trade_ExitNO.txt')):
                os.rename(str_path_dir_Config + '\Trade_ExitNO.txt', str_path_dir_Config + '\Trade_Exit.txt')
            return
        int_counter = int_counter + 1
        time.sleep(60)  # delay time
        print('countdown delay: ' + str(int_runtime_minutes - int_counter))

    #print('exiting trade process.')
    if (os.path.isfile(str_path_dir_Config + '\Trade_ExitNO.txt')):
        os.rename(str_path_dir_Config + '\Trade_ExitNO.txt', str_path_dir_Config + '\Trade_Exit.txt')
    print('finish trade cycle.')

if __name__ == "__main__":

    # sys.exit()  # Exit

    #subprocess.Popen(["python.exe", "Main_Trade.py"])

    global dt_trading_timestamp

    # set path of working directories and files
    str_path_dir_Config = os.getcwd() + "\Config"
    str_path_dir_Data = os.getcwd() + "\Data"

    # Easter Times
    func_run_process(7, 30, 60)
    func_run_process(9, 0, 60)
    func_run_process(12, 0, 60)
    func_run_process(15, 30, 60)

    if not (os.path.isfile(str_path_dir_Config + '\Scheduler_Exit.txt')):
        print("delay 15 minutes for scheduler process to finish.")
        time.sleep(15 * 60)  # delay time
    print('finish scheduler cycle.')

    if (os.path.isfile(str_path_dir_Config + '\Scheduler_Exit.txt')):
        os.rename(str_path_dir_Config + '\Scheduler_Exit.txt', str_path_dir_Config + '\Scheduler_ExitNO.txt')  # Ready to start the process again
    print('The End.')

    sys.exit()  # Exit

# Main_Scheduler.py
# The End
