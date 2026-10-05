"""Local startup refuses busy ports and stops its owned process tree."""
import socket
import subprocess
import sys
import unittest
import psutil
from start import available, stop_process


class StartupTests(unittest.TestCase):
    def test_busy_port_is_rejected_without_stopping_the_existing_listener(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            with self.assertRaisesRegex(RuntimeError, 'already in use'):
                available(listener.getsockname()[1])
            self.assertGreater(listener.fileno(), -1)

    def test_shutdown_stops_children_of_the_python_launcher(self):
        command = ('import subprocess,sys,time; '
                   'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(90)"]); '
                   'print(child.pid,flush=True);time.sleep(90)')
        child = subprocess.Popen([sys.executable, '-c', command], stdout=subprocess.PIPE, text=True)
        try:
            grandchild = int(child.stdout.readline().strip())
            self.assertTrue(psutil.pid_exists(grandchild))
            stop_process(child)
            self.assertIsNotNone(child.poll())
            self.assertFalse(psutil.pid_exists(grandchild))
        finally:
            stop_process(child)
            child.stdout.close()
