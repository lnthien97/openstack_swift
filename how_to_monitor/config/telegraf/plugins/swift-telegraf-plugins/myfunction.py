#!/usr/bin/python
import os, sys, subprocess, socket, yaml, json, time, re

def call_cmd(cmd):
        process = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE)
        content = process.communicate()[0].rstrip()
        return str(content)

def write_log(log_type):
        logger = logging.getLogger(log_type)
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler('/var/log/'+log_type+'.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        return logger

def matchObj(regex, data):
    matchObj = re.match( regex, data, re.M|re.I)
    return matchObj

