import os
import os.path
import time
import subprocess
import grpc
import pb.fc_g_pb2_grpc
import pb.fc_g_pb2
import pb.fc_x_pb2_grpc
import pb.fc_x_pb2
import fc.node
import weakref

# for cleanup after exit.
from concurrent import futures
import signal
import ctypes

# Start up the Go executable and create a bi-directional gRPC API with a server in Go
# and a server in python and each side creating clients to respective servers.
class Driver():

    def __init__(self, sock_file=None):
        self.g_proc = None
        cwd = os.getcwd()
        self.sock_file = sock_file if sock_file else f'{cwd}/fc-lang.sock'
        self.x_sock_file = f'{cwd}/fc-x.sock'
        if os.path.exists(self.sock_file):
            os.remove(self.sock_file)
        if os.path.exists(self.x_sock_file):
            os.remove(self.x_sock_file)

    def load(self):
        if self.g_proc:
            raise Exception("fc-lang already loaded")

        # TODO: at a minimum, nodes do not survive, they get claimed during the
        # selection navigation
        self.handles = {} #weakref.WeakValueDictionary()
        self.start_x_server()
        self.start_g_proc()
        self.create_g_client()

    def start_g_proc(self):
        exec_bin = os.environ.get('FC_LANG_EXEC', 'fc-lang')
        cmd = [exec_bin, self.sock_file, self.x_sock_file]
        dbg_addr = os.environ.get('FC_LANG_DBG_ADDR')
        if dbg_addr:
            dbg = ['dlv', f'--listen={dbg_addr}', '--headless=true', '--api-version=2', 'exec']
            dbg.extend(cmd)
            cmd = dbg
        self.g_proc = subprocess.Popen(cmd, preexec_fn=exit_with_parent)

        i = 0
        while i < 20 or dbg_addr:
            if os.path.exists(self.sock_file):
                return
            time.sleep(0.05)
            i = i + 1
        raise Exception("failure to start fc-yang")

    def create_g_client(self):
        self.g_channel = grpc.insecure_channel(f'unix://{self.sock_file}')
        self.g_handles = pb.fc_g_pb2_grpc.HandlesStub(self.g_channel)
        self.g_parser = pb.fc_g_pb2_grpc.ParserStub(self.g_channel)
        self.g_nodes = pb.fc_g_pb2_grpc.NodeStub(self.g_channel)
        self.g_nodeutil = pb.fc_g_pb2_grpc.NodeUtilStub(self.g_channel)
        self.g_device = pb.fc_g_pb2_grpc.DeviceStub(self.g_channel)
        self.g_restconf = pb.fc_g_pb2_grpc.RestconfStub(self.g_channel)

    def start_x_server(self):
        self.x_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        self.x_node_service = fc.node.XNodeServicer(self)
        pb.fc_x_pb2_grpc.add_XNodeServicer_to_server(self.x_node_service, self.x_server)
        self.x_server.add_insecure_port(f'unix://{self.x_sock_file}')
        self.x_server.start()

    def unload(self):
        self.handles = None
        self.x_server.stop(1).wait()
        self.g_proc.terminate()
        self.g_proc.wait()
        self.g_proc = None


# Ensure fc-lang is terminated when this python process is terminated
# see
#  https://stackoverflow.com/questions/19447603/how-to-kill-a-python-child-process-created-with-subprocess-check-output-when-t/19448096#19448096
#
# does not work on windows, not sure about mac, need to implement different method.
#
libc = ctypes.CDLL("libc.so.6")
def exit_with_parent():
    return libc.prctl(1, signal.SIGTERM)
