#!/usr/bin/env python3
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
runpy.run_path(os.path.join(HERE, 'restore_header_baseline_remove_extras.py'), run_name='__main__')
