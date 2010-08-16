import sys
import os
import copy

import yaku.tools

from yaku.task \
    import \
        Task
from yaku.task_manager \
    import \
        extension, create_tasks, CompiledTaskGen
from yaku.utils \
    import \
        find_deps, ensure_dir
from yaku.compiled_fun \
    import \
        compile_fun

ccompile, cc_vars = compile_fun("cc", "${CC} ${CFLAGS} ${INCPATH} ${CC_TGT_F}${TGT[0].abspath()} ${CC_SRC_F}${SRC}", False)

ccprogram, ccprogram_vars = compile_fun("ccprogram", "${LINK} ${LINKFLAGS} ${LINK_TGT_F}${TGT[0].abspath()} ${LINK_SRC_F}${SRC} ${APP_LIBDIR} ${APP_LIBS}", False)

cshlink, cshlink_vars = compile_fun("cshlib", "${SHLINK} ${SHLINKFLAGS} ${APP_LIBDIR} ${APP_LIBS} ${SHLINK_TGT_F}${TGT[0]} ${SHLINK_SRC_F}${SRC}", False)

clink, clink_vars = compile_fun("clib", "${STLINK} ${STLINKFLAGS} ${STLINK_TGT_F}${TGT[0].abspath()} ${STLINK_SRC_F}${SRC}", False)

@extension('.c')
def c_hook(self, node):
    tasks = ccompile_task(self, node)
    self.object_tasks.extend(tasks)
    return tasks

def ccompile_task(self, node):
    folder, base = os.path.split(node.bld_base())
    tmp = folder + os.path.sep + self.env["CC_OBJECT_FMT"] % base
    target = node.ctx.bldnode.declare(tmp)
    ensure_dir(target.abspath())

    task = Task("cc", inputs=[node], outputs=[target])
    task.gen = self
    task.env_vars = cc_vars
    #print find_deps("foo.c", ["."])
    #task.scan = lambda : find_deps(node, ["."])
    #task.deps.extend(task.scan())
    task.env = self.env
    task.func = ccompile
    return [task]

def shlink_task(self, name):
    objects = [tsk.outputs[0] for tsk in self.object_tasks]
    target = os.path.join(self.env["BLDDIR"], name + ".so")
    ensure_dir(target)

    task = Task("cc_shlink", inputs=objects, outputs=target)
    task.gen = self
    task.env = self.env
    task.func = cshlink
    task.env_vars = cshlink_vars
    return [task]

def static_link_task(self, name):
    objects = [tsk.outputs[0] for tsk in self.object_tasks]

    folder, base = os.path.split(name)
    tmp = folder + os.path.sep + self.env["STATICLIB_FMT"] % base
    target = self.bld.bld_root.declare(tmp)
    ensure_dir(target.abspath())

    task = Task("cc_link", inputs=objects, outputs=[target])
    task.gen = self
    task.env = self.env
    task.func = clink
    task.env_vars = clink_vars
    return [task]

def ccprogram_task(self, name):
    objects = [tsk.outputs[0] for tsk in self.object_tasks]
    def declare_target():
        folder, base = os.path.split(name)
        tmp = folder + os.path.sep + self.env["PROGRAM_FMT"] % base
        return self.bld.bld_root.declare(tmp)
    target = declare_target()
    ensure_dir(target.abspath())

    task = Task("ccprogram", inputs=objects, outputs=[target])
    task.gen = self
    task.env = self.env
    task.func = ccprogram
    task.env_vars = ccprogram_vars
    return [task]

def apply_cpppath(task_gen):
    paths = task_gen.env["CPPPATH"]
    task_gen.env["INCPATH"] = [
            task_gen.env["CPPPATH_FMT"] % p for p in paths]

def apply_libs(task_gen):
    libs = task_gen.env["LIBS"]
    task_gen.env["APP_LIBS"] = [
            task_gen.env["LIB_FMT"] % lib for lib in libs]

def apply_libdir(task_gen):
    libdir = task_gen.env["LIBDIR"]
    task_gen.env["APP_LIBDIR"] = [
            task_gen.env["LIBDIR_FMT"] % d for d in libdir]

class CCBuilder(object):
    def __init__(self, ctx):
        self.ctx = ctx
        self.env = copy.deepcopy(ctx.env)

    def ccompile(self, name, sources, env=None):
        _env = copy.deepcopy(self.env)
        if env is not None:
            _env.update(env)

        task_gen = CompiledTaskGen("cccompile", sources, name)
        task_gen.bld = self.ctx
        task_gen.env = _env
        apply_cpppath(task_gen)

        tasks = create_tasks(task_gen, sources)
        for t in tasks:
            t.env = task_gen.env
        self.ctx.tasks.extend(tasks)

        outputs = []
        for t in tasks:
            outputs.extend(t.outputs)
        return outputs

    def static_library(self, name, sources, env=None):
        _env = copy.deepcopy(self.env)
        if env is not None:
            _env.update(env)

        sources = [self.ctx.src_root.find_resource(s) for s in sources]
        task_gen = CompiledTaskGen("ccstaticlib", sources, name)
        task_gen.bld = self.ctx
        task_gen.env = _env
        apply_cpppath(task_gen)
        apply_libdir(task_gen)
        apply_libs(task_gen)

        tasks = create_tasks(task_gen, sources)
        ltask = static_link_task(task_gen, name)
        tasks.extend(ltask)
        for t in tasks:
            t.env = task_gen.env
        self.ctx.tasks.extend(tasks)

        outputs = []
        for t in ltask:
            outputs.extend(t.outputs)
        return outputs


    def program(self, name, sources, env=None):
        _env = copy.deepcopy(self.env)
        if env is not None:
            _env.update(env)

        sources = [self.ctx.src_root.find_resource(s) for s in sources]
        task_gen = CompiledTaskGen("ccprogram", sources, name)
        task_gen.env = _env
        task_gen.bld = self.ctx
        apply_cpppath(task_gen)
        apply_libdir(task_gen)
        apply_libs(task_gen)

        tasks = create_tasks(task_gen, sources)
        ltask = ccprogram_task(task_gen, name)
        tasks.extend(ltask)
        for t in tasks:
            t.env = task_gen.env
        self.ctx.tasks.extend(tasks)

        outputs = []
        for t in ltask:
            outputs.extend(t.outputs)
        return outputs

def configure(ctx):
    if sys.platform == "win32":
        candidates = ["msvc", "gcc"]
    else:
        candidates = ["gcc", "cc"]

    def _detect_cc():
        detected = None
        sys.path.insert(0, os.path.dirname(yaku.tools.__file__))
        try:
            for cc_type in candidates:
                sys.stderr.write("Looking for %s... " % cc_type)
                try:
                    mod = __import__(cc_type)
                    if mod.detect(ctx):
                        sys.stderr.write("yes\n")
                        detected = cc_type
                        break
                except:
                    pass
                sys.stderr.write("no!\n")
            return detected
        finally:
            sys.path.pop(0)

    cc_type = _detect_cc()
    if cc_type is None:
        raise ValueError("No C compiler found!")
    cc = ctx.load_tool(cc_type)
    cc.setup(ctx)

    if sys.platform == "win32":
        raise NotImplementedError("cstatic lib not supported yet")
    else:
        ar = ctx.load_tool("ar")
        ar.setup(ctx)

def get_builder(ctx):
    return CCBuilder(ctx)
