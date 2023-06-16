import fc.pb.fc_pb2
import fc.pb.fc_pb2_grpc
import fc.meta_decoder
import fc.handles

class Parser():

    def __init__(self, driver):
        self.driver = driver

    def load_module(self, dir, name):
        req = fc.pb.fc_pb2.LoadModuleRequest(dir=dir, name=name)
        resp = self.driver.g_parser.LoadModule(req)
        m = fc.meta_decoder.Decoder().decode(resp.module)
        m.hnd = self.driver.obj_weak.store_hnd(resp.moduleHnd, m)
        return m
    
    @classmethod
    def resolve_module(cls, driver, module_hnd_id):
        m = driver.obj_weak.lookup_hnd(module_hnd_id)
        if m == None:
            req = fc.pb.fc_pb2.GetModuleRequest(moduleHnd=module_hnd_id)
            resp = driver.g_nodes.GetModule(req)
            m = fc.meta_decoder.Decoder().decode(resp.module)
            m.hnd = driver.obj_weak.store_hnd(module_hnd_id, m)
        return m
