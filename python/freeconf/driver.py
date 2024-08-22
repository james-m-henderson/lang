import os
import os.path
import time
import subprocess
import grpc
import freeconf.pb.fc_pb2_grpc
import freeconf.pb.fc_pb2
import freeconf.pb.fc_x_pb2_grpc
import freeconf.pb.fc_x_pb2
import freeconf.pb.fs_pb2_grpc
import freeconf.pb.fs_pb2
import freeconf.node
import freeconf.fs
import freeconf
import weakref
import platform
import shutil
from contextlib import contextmanager
import signal
import ctypes
from ctypes.util import find_library

from concurrent import futures
import logging

logger = logging.getLogger(__name__)

instance = None

def shared_instance():
    """ shared instance of Driver.  Applications generally just need a single instance and so
        this would be typical access unless 
    """
    global instance
    if instance is None:
        instance = Driver()
        instance.load()
    return instance

def exe_fname():
    os_name = platform.system().lower()
    py_arch = platform.machine().lower()
    exe_ext = ""
    if os_name == "windows":
        exe_ext = ".exe"
    arch = {
        "x86_64": "amd64",
    }.get(py_arch, py_arch)
    fname = f'fc-lang-{freeconf.__version__}-{os_name}-{arch}{exe_ext}'
    return fname

def home_bin_dir():
    return os.path.expanduser("~/.freeconf/bin")  # works on windows too

class ExecNotFoundException(Exception):
    def __init__(self, msg):
        super().__init__(msg)

def path_to_exe(verbose=False):
    """
    Rules for finding fc-lang exe.  We are somewhat flexible because we want to make it
    usable in all environments without too much hassle, but not at the expense of being
    too magical.  Hopefully this is the right balance.
    
        1. If explicitly set exact exec filename using FC_LANG_EXEC env var, use that only
        2. If explicitly set dir to set of exes using FC_LANG_DIR env var, use that only
        3. Look in ~/.freeconf/bin 
        4. Look in PATH
        5. Fail
    """
    file_path = os.environ.get('FC_LANG_EXEC', None)
    if file_path:
        logger.debug(f"FC_LANG_EXEC set. Checking {file_path}...")
        if not os.path.isfile(file_path):
            raise ExecNotFoundException(f"FC_LANG_EXEC={file_path} does not point to a valid file")
        return file_path

    fname = exe_fname()
    fc_lang_dir = os.environ.get('FC_LANG_DIR', None)
    fc_dir = home_bin_dir() if fc_lang_dir is None else fc_lang_dir
    file_path = os.path.join(fc_dir, fname)
    logger.debug(f"Checking {file_path} for fc-lang executable")
    if os.path.isfile(file_path):
        return file_path
    elif fc_lang_dir is not None:
        # if FC_LANG_DIR is set and the file is not found, raise an error
        raise ExecNotFoundException(f"{file_path} was not found in {fc_lang_dir}")
    
    logger.debug("Checking PATH for fc-lang executable")
    full_path = shutil.which(fname)
    if not full_path:
        raise ExecNotFoundException(f"{fname} was not found in PATH or any of the other documented locations")

    return full_path

class Driver:

    def __init__(self, sock_file=None, x_sock_file=None):
        logger.debug("Initializing Driver")
        self.g_proc = None
        cwd = os.getcwd()
        self.sock_file = sock_file if sock_file else f'{cwd}/fc-lang.sock'
        self.x_sock_file = x_sock_file if x_sock_file else f'{cwd}/fc-x.sock'
        self.dbg_addr = os.environ.get('FC_LANG_DBG_ADDR')
        self.cleanup_sockets()

    def cleanup_sockets(self):
        logger.debug("Cleaning up any existing socket files")
        if os.path.exists(self.sock_file):
            os.remove(self.sock_file)
        if os.path.exists(self.x_sock_file):
            os.remove(self.x_sock_file)

    def load(self, test_harness=None):
        logger.debug("Loading Driver")
        if self.g_proc:
            raise Exception("fc-lang already loaded")

        self.obj_strong = HandlePool(self, False)  # objects that have an explicit release/destroy
        self.obj_weak = HandlePool(self, True)  # objects that should disappear on their own

        self.start_x_server(test_harness)
        if test_harness is None:
            self.start_g_proc()
        self.wait_for_g_connection(self.dbg_addr is not None)
        self.create_g_client()

    def start_g_proc(self):
        exec_bin = path_to_exe()
        cmd = [exec_bin, self.sock_file, self.x_sock_file, '--trace']
        if self.dbg_addr:
            dbg = ['dlv', f'--listen={self.dbg_addr}', '--headless=true', '--api-version=2', 'exec']
            dbg.extend(cmd)
            cmd = dbg
        logger.debug(f"Starting Go process with command: {' '.join(cmd)}")
        self.g_proc = subprocess.Popen(cmd, preexec_fn=set_pdeathsig())

    def wait_for_g_connection(self, wait_forever):
        logger.debug(f"Waiting for Go process to create socket file: {self.sock_file}")
        i = 0
        while i < 20 or wait_forever:
            if os.path.exists(self.sock_file):
                logger.debug(f"Socket file {self.sock_file} created by Go process")
                time.sleep(0.1)
                return
            time.sleep(0.5)
            i += 1
        logger.error(f"Timed out waiting for {self.sock_file} file")
        raise Exception(f'timed out waiting for {self.sock_file} file')

    def create_g_client(self):
        logger.debug(f"Creating gRPC clients for Go server on socket: {self.sock_file}")
        self.g_channel = grpc.insecure_channel(f'unix://{self.sock_file}')
        self.g_handles = freeconf.pb.fc_pb2_grpc.HandlesStub(self.g_channel)
        self.g_parser = freeconf.pb.fc_pb2_grpc.ParserStub(self.g_channel)
        self.g_nodes = freeconf.pb.fc_pb2_grpc.NodeStub(self.g_channel)
        self.g_nodeutil = freeconf.pb.fc_pb2_grpc.NodeUtilStub(self.g_channel)
        self.g_device = freeconf.pb.fc_pb2_grpc.DeviceStub(self.g_channel)
        self.g_proto = freeconf.pb.fc_pb2_grpc.ProtoStub(self.g_channel)
        self.g_fs = freeconf.pb.fs_pb2_grpc.FileSystemStub(self.g_channel)
        self.fs = freeconf.fs.FileSystemServicer(self)
        logger.debug("gRPC clients created successfully")

    def start_x_server(self, test_harness=None):
        logger.debug(f"Starting Python gRPC server on socket: {self.x_sock_file}")
        self.x_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        self.x_node_service = freeconf.node.XNodeServicer(self)
        freeconf.pb.fc_x_pb2_grpc.add_XNodeServicer_to_server(self.x_node_service, self.x_server)
        if test_harness:
            freeconf.pb.fc_test_pb2_grpc.add_TestHarnessServicer_to_server(test_harness, self.x_server)
        self.x_server.add_insecure_port(f'unix://{self.x_sock_file}')
        self.x_server.start()
        logger.debug(f"Python gRPC server started on {self.x_sock_file}")

    def unload(self):
        logger.debug("Unloading Driver and stopping services")
        self.obj_weak.release()
        self.obj_strong.release()
        self.x_server.stop(1).wait()
        self.g_proc.terminate()
        self.g_proc.wait()
        self.g_proc = None
        logger.debug("Driver unloaded successfully")


class HandlePool:
    def __init__(self, driver, weak):
        self.weak = weak
        self.driver = driver
        self.handles = weakref.WeakValueDictionary() if self.weak else {}
        logger.debug(f"HandlePool initialized with weak={self.weak}")

    def lookup_hnd(self, id):
        logger.debug(f"Looking up handle with ID: {id}")
        return self.handles.get(id, None)

    def require_hnd(self, id):
        logger.debug(f"Requiring handle with ID: {id}")
        try:
            return self.handles[id]
        except KeyError:
            logger.error(f"Could not resolve handle with ID: {id}")
            raise KeyError(f'could not resolve hnd {id}')

    def store_hnd(self, id, obj):
        logger.debug(f"Storing handle with ID: {id}")
        if id == 0:
            logger.error("Attempted to store handle with invalid ID: 0")
            raise Exception("0 id not valid")
        self.handles[id] = obj
        if self.weak:
            weakref.finalize(obj, self.release_hnd, id)
        return id

    def release_hnd(self, id):
        logger.debug(f"Releasing handle with ID: {id}")
        if self.handles is not None:
            self.driver.g_handles.Release(freeconf.pb.fc_pb2.ReleaseRequest(hnd=id))

    def release(self):
        logger.debug("Releasing all handles")
        self.handles = None

def set_pdeathsig(sig=signal.SIGTERM):
    system = platform.system().lower()

    if system == "linux":
        # Linux-specific implementation using prctl and PR_SET_PDEATHSIG
        libc = ctypes.CDLL("libc.so.6", use_errno=True)

        def prctl_deathsig():
            if libc.prctl(1, sig) != 0:
                raise OSError(ctypes.get_errno(), "Failed to set PR_SET_PDEATHSIG")
        
        return prctl_deathsig

    elif system == "darwin":  # macOS
        # macOS-specific implementation
        libc = ctypes.CDLL(find_library("c"))

        def set_pdeathsig_mac():
            # Try to set the process group ID
            try:
                libc.setpgid(0, 0)  # Set the process group ID to the child process's PID
            except Exception as e:
                pass  # If this fails, the signal might not be set correctly
        
        return set_pdeathsig_mac

    else:
        # Other systems: You can either add more cases or use a fallback
        raise NotImplementedError(f"set_pdeathsig not implemented for {system}")