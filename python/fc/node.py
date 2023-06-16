import queue
import grpc
import threading
import fc.pb.fc_pb2
import fc.pb.common_pb2
import fc.pb.fc_pb2_grpc
import fc.pb.fc_x_pb2
import fc.pb.fc_x_pb2_grpc
import fc.meta
import fc.val
import fc.parser
import traceback

class Selection():

    def __init__(self, driver, hnd_id, node, path, browser, inside_list=False):
        self.driver = driver
        self.hnd = driver.obj_strong.store_hnd(hnd_id, self)
        self.node = node
        self.path = path
        self.browser = browser
        self.inside_list = inside_list

    @classmethod
    def resolve(cls, driver, hnd_id):
        sel = driver.obj_strong.lookup_hnd(hnd_id)
        if sel == None:
            req = fc.pb.fc_pb2.GetSelectionRequest(selHnd=hnd_id)
            resp = driver.g_nodes.GetSelection(req)
            node = resolve_node_hnd(driver, resp.nodeHnd, resp.remoteNode)
            if not node:
                raise Exception(f"sel:{hnd_id} node:{resp.nodeHnd} not found. is remote={resp.remoteNode}")
            path = fc.meta.Path.resolve(driver, resp.path)
            browser = Browser.resolve(driver, resp.browserHnd)
            sel = Selection(driver, hnd_id, node, path, browser, resp.insideList)
        return sel

    def action(self, inputNode=None):
        input_hnd = 0        
        if inputNode:
            input_hnd = ensure_node_hnd(self.driver, inputNode)
        req = fc.pb.fc_pb2.ActionRequest(selHnd=self.hnd, inputNodeHnd=input_hnd)
        resp = self.driver.g_nodes.Action(req)
        outputSel = None
        if resp.outputSelHnd:
            outputSel = Selection.resolve(self.driver, resp.outputSelHnd)
        return outputSel


    def notification(self, callback):
        req = fc.pb.fc_pb2.NotificationRequest(selHnd=self.hnd)
        stream = self.driver.g_nodes.Notification(req)
        def rdr():
            try:
                for resp in stream:
                    if resp == None:
                        return
                    msg = Selection.resolve(self.driver, resp.selHnd)
                    callback(msg)
            except grpc.RpcError as gerr:
                if not gerr.cancelled():
                    print(f'grpc err. {gerr}')
            except Exception as e:
                print(f'got error in callback delivering msg: {type(e)} {e}')

        t = threading.Thread(target=rdr)
        t.start()
        def closer():
            stream.cancel()
            t.join()
        return closer

    def upsert_into(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.UPSERT_INTO, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def upsert_from(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.UPSERT_FROM, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def insert_from(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.INSERT_FROM, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def insert_into(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.INSERT_INTO, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def upsert_into_set_defaults(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.UPSERT_INTO_SET_DEFAULTS, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def upsert_from_set_defaults(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.UPSERT_FROM_SET_DEFAULTS, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def update_into(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.UPDATE_INTO, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def update_from(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.UPDATE_FROM, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def replace_from(self, n):
        node_hnd = ensure_node_hnd(self.driver, n)
        req = fc.pb.fc_pb2.SelectionEditRequest(op=fc.pb.fc_pb2.REPLACE_FROM, selHnd=self.hnd, nodeHnd=node_hnd)        
        self.driver.g_nodes.SelectionEdit(req)

    def find(self, path):
        req = fc.pb.fc_pb2.FindRequest(selHnd=self.hnd, path=path)
        resp = self.driver.g_nodes.Find(req)
        return Selection.resolve(self.driver, resp.selHnd)


def resolve_node_hnd(driver, hnd, is_remote):
    if not hnd:
        return None
    n = driver.obj_strong.lookup_hnd(hnd)
    if n == None and is_remote:
        n = fc.handles.RemoteRef(driver, hnd)
    elif n == None: 
        raise Exception("not remote and not found\n" + traceback.format_exc())

    return n

def ensure_node_hnd(driver, n):
    if n == None:
        # nil node
        return None
    if not n.hnd:
        # unregistered local node about to be registered with go
        resp = driver.g_nodes.NewNode(fc.pb.fc_pb2.NewNodeRequest())
        n.hnd = driver.obj_strong.store_hnd(resp.nodeHnd, n)
    return n.hnd


class Browser():

    def __init__(self, driver, module, node=None, node_src=None, hnd_id=None):
        self.driver = driver
        if hnd_id == None:
            node_hnd = ensure_node_hnd(driver, node)
            req = fc.pb.fc_pb2.NewBrowserRequest(moduleHnd=module.hnd, nodeHnd=node_hnd)
            resp = self.driver.g_nodes.NewBrowser(req)
            self.hnd = driver.obj_weak.store_hnd(resp.browserHnd, self)
        else:
            self.hnd = driver.obj_weak.store_hnd(hnd_id, self)
        self.module = module
        self.node_src = node_src
        self.node_obj = node

    def node(self):
        if self.node_src:
            return self.node_src()
        return self.node_obj

    def root(self):
        g_req = fc.pb.fc_pb2.BrowserRootRequest(browserHnd=self.hnd)
        resp = self.driver.g_nodes.BrowserRoot(g_req)
        return Selection.resolve(self.driver, resp.selHnd)

    @classmethod
    def resolve(cls, driver, hnd_id):
        b = driver.obj_weak.lookup_hnd(hnd_id)
        if b == None:
            req = fc.pb.fc_pb2.GetBrowserRequest(browserHnd=hnd_id)
            resp = driver.g_nodes.GetBrowser(req)
            module = fc.parser.Parser.resolve_module(driver, resp.moduleHnd)
            b = Browser(driver, module, hnd_id=hnd_id)
        return b


class ChildRequest():

    def __init__(self, sel, meta, new, delete):
        self.sel = sel
        self.meta = meta
        self.new = new
        self.delete = delete

class ActionRequest():

    def __init__(self, sel, meta, input):
        self.sel = sel
        self.meta = meta
        self.input = input        

class ListRequest():

    def __init__(self, sel, meta, new, delete, row, first, key):
        self.sel = sel
        self.meta = meta
        self.new = new
        self.delete = delete
        self.row = row
        self.first = first
        self.key = key

class FieldRequest():

    def __init__(self, sel, meta, write, clear):
        self.sel = sel
        self.meta = meta
        self.write = write
        self.clear = clear

class NotificationRequest():

    def __init__(self, sel, meta, queue):
        self.sel = sel
        self.meta = meta
        self.queue = queue

    def send(self, node):
        self.queue.put(node)


class NodeRequest():

    def __init__(self, sel, new=False, delete=False):
        self.sel = sel
        self.new = new
        self.delete = delete


class XNodeServicer(fc.pb.fc_x_pb2_grpc.XNodeServicer):
    """Bridge between python node navigation and go node navigation"""

    def __init__(self, driver):
        self.driver = driver

    def XContext(self, g_req, context):
        try:
            sel = Selection.resolve(self.driver, g_req.selHnd)
            sel.node.context(sel)
            return fc.pb.fc_x_pb2.XContextResponse()
        except Exception as error:
            print(traceback.format_exc())
            raise error

    def XRelease(self, g_req, context):
        try:
            sel = Selection.resolve(self.driver, g_req.selHnd)
            self.driver.obj_weak.release_hnd(sel.node.hnd)
            sel.node.release(sel)

            # this ensures that if python still retains a reference to node and
            # reuses it, Go will ask for the node again and restore it in it's handle pool
            sel.node.hnd = 0  

            return fc.pb.fc_x_pb2.XReleaseResponse()
        except Exception as error:
            print(traceback.format_exc())
            raise error

    def XChoose(self, g_req, context):
        try:
            sel = Selection.resolve(self.driver, g_req.selHnd)
            choice = fc.meta.get_choice(sel.path.meta, g_req.choiceIdent)
            choice_case = sel.node.choose(sel, choice)
            if choice_case is None:
                return fc.pb.fc_x_pb2.XChooseResponse()
            return fc.pb.fc_x_pb2.XChooseResponse(caseIdent=choice_case.ident)
        except Exception as error:
            print(traceback.format_exc())
            raise error
        

    def XNext(self, g_req, context):
        try:
            sel = Selection.resolve(self.driver, g_req.selHnd)
            meta = sel.path.meta
            key_in = None
            if g_req.key != None:
                key_in = []
                for g_key_val in g_req.key:
                    key_in.append(fc.val.proto_decode(g_key_val))

            req = ListRequest(sel, meta, g_req.new, g_req.delete, g_req.row, g_req.first, key_in)
            child, key_out = sel.node.next(req)
            if child != None:
                child_hnd = ensure_node_hnd(self.driver, child)
                g_key_out = None
                if key_out != None:
                    for v in key_out:
                        g_key_out.append(fc.val.proto_encode(v))
                return fc.pb.fc_x_pb2.XNextResponse(nodeHnd=child_hnd, key=g_key_out)
            else:
                return fc.pb.fc_x_pb2.XNextResponse()
        except Exception as error:
            print(traceback.format_exc())
            raise error
        

    def XChild(self, g_req, context):
        try:
            sel = Selection.resolve(self.driver, g_req.selHnd)
            meta = fc.meta.get_def(sel.path.meta, g_req.metaIdent)
            req = ChildRequest(sel, meta, g_req.new, g_req.delete)
            child = sel.node.child(req)
            child_hnd = None
            if child != None:
                child_hnd = ensure_node_hnd(self.driver, child)
            return fc.pb.fc_x_pb2.XChildResponse(nodeHnd=child_hnd)
        except Exception as error:
            print(traceback.format_exc())
            raise error

    def XField(self, g_req, context):
        try:
            sel = Selection.resolve(self.driver, g_req.selHnd)
            meta = fc.meta.get_def(sel.path.meta, g_req.metaIdent)
            req = FieldRequest(sel, meta, g_req.write, g_req.clear)
            write_val = None
            if g_req.write:
                if not g_req.clear:
                    write_val = fc.val.proto_decode(g_req.toWrite)
            read_val = sel.node.field(req, write_val)
            if not g_req.write:
                fromRead = fc.val.proto_encode(read_val)
                resp = fc.pb.fc_x_pb2.XFieldResponse(fromRead=fromRead)
            else:
                resp = fc.pb.fc_x_pb2.XFieldResponse()
            return resp
        except Exception as error:
            print(traceback.format_exc())
            raise error

    def XSelect(self, g_req, context):
        # TODO
        pass

    def XAction(self, g_req, context):
        try:
            sel = Selection.resolve(self.driver, g_req.selHnd)
            meta = sel.path.meta
            input = None
            if g_req.inputSelHnd != 0:
                input = Selection.resolve(self.driver, g_req.inputSelHnd)
            output = sel.node.action(ActionRequest(sel, meta, input))
            output_node_hnd = ensure_node_hnd(self.driver, output)
            return fc.pb.fc_x_pb2.XActionResponse(outputNodeHnd=output_node_hnd)
        except Exception as error:
            print(traceback.format_exc())
            raise error


    def XNodeSource(self, g_req, context):
        browser = fc.node.Browser.resolve(self.driver, g_req.browserHnd)
        node_hnd = ensure_node_hnd(self.driver, browser.node())
        return fc.pb.fc_x_pb2.XNodeSourceResponse(nodeHnd=node_hnd)


    def XNotification(self, g_req, context):
        q = queue.Queue()
        sel = Selection.resolve(self.driver, g_req.selHnd)
        meta = sel.path.meta
        closer = sel.node.notification(NotificationRequest(sel, meta, q))
        def stream_closed():
            q.put(None)
        context.add_callback(stream_closed)
        try:
            while True:
                node = q.get()
                if node == None:
                    break
                node_hnd = ensure_node_hnd(self.driver, node)
                yield fc.pb.fc_x_pb2.XNotificationResponse(nodeHnd=node_hnd)
                q.task_done()
        finally:
            closer()
        return None
    
    def XBeginEdit(self, g_req, context):
        sel = Selection.resolve(self.driver, g_req.selHnd)
        sel.node.begin_edit(NodeRequest(sel, new=g_req.new, delete=g_req.delete))
        return fc.pb.fc_x_pb2.XBeginEditResponse()

    def XEndEdit(self, g_req, context):
        sel = Selection.resolve(self.driver, g_req.selHnd)
        sel.node.end_edit(NodeRequest(sel, new=g_req.new, delete=g_req.delete))
        return fc.pb.fc_x_pb2.XEndEditResponse()
