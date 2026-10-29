# -*- coding: utf-8 -*-
NODE_INFO = {
    "name": "裙子毛囊 Rig 生成器",
    "description": (
        "按骨骼位置批量生成裙子的毛囊驱动 Rig：合并面片并自动投影 UV、"
        "面片上建毛囊、两层空组 + 父对象约束、方块（FK）与圆（单节）控制器，"
        "最后约束骨骼。运行前选中每条裙链的第一个关节。"
    ),
    "author": "禾洛",
    "version": "1.0.1",
    "node": "skirtFolRigNode",
    "node_id": "0x00151503",
    "category": "rigging",
    "tags": ["绑定", "裙子", "毛囊", "程序化"],
    "maya_versions": ["2018", "2020", "2022", "2023", "2024", "2025"],
    "github": "https://github.com/MengXingXiaoMing/maya-node-plugin-market",
    "run": "cmds.skirtFolRig()",
}

"""skirtFolRig - 裙子毛囊 Rig 生成器

生成的节点结构（以骨骼 XXX 为例）：
    fk_XXX_plan                       全部面片合并成一个 mesh（自动投影 UV）
    fk_ctrl_XXX_loc_fol               毛囊 transform（t/r ← 毛囊输出）
      └ fk_ctrl_XXX_loc_folGroup      毛囊下层组（0 层）
    fk_ctrl_XXX_loc_folGrp            空组第一层（静态对齐骨骼，按链嵌套）
      └ fk_ctrl_XXX_loc_folgrp        空组第二层（0 层）← 被毛囊下层组约束
          └─connect t/r/s─→ fk_driver_XXX_grp
    fk_zero_XXX_grp → fk_driver_XXX_grp → fk_ctrl_XXX        方块（0.5）
        └ ik_zero_XXX_grp → ik_driver_XXX_grp → ik_ctrl_XXX  圆（1.0）→ 约束骨骼

用法：
    maya.cmds.skirtFolRig()            按当前选择（每链首个关节）生成
    maya.cmds.skirtFolRig(ui=True)     打开窗口
    maya.cmds.skirtFolRig(clean=True)  只清理生成物
"""

import maya.api.OpenMaya as om
import maya.cmds as cmds
import sys

# ------------------------- 可调参数 -------------------------
PLAN_SIZE = 0.01
BOX_SIZE = 0.5
CIR_SIZE = 1.0
CTRL_COLOR_BOX = 13
CTRL_COLOR_CIR = 6
GRP_ROOT = "Skirt_Grp"
GRP_DRIVER = "body_ikfk_dr_grp"
GRP_CTRL = "skirt_ikfi_ctrl_grp"
SCALE_REF = "local_C0_ctl"
TAG = "skirt_fol_rig"
# -----------------------------------------------------------


def maya_useNewAPI():
    pass


def _log(m):
    sys.stderr.write("[skirtFolRig] %s\n" % m)


def _tag(node):
    if not cmds.attributeQuery(TAG, node=node, exists=True):
        cmds.addAttr(node, ln=TAG, at="bool", dv=1, k=False)
        cmds.setAttr(node + "." + TAG, lock=True)


def _ensure_grp(name):
    if cmds.objExists(name):
        return name
    g = cmds.group(em=True, n=name)
    _tag(g)
    return g


def _make_curve(kind, name, size, color):
    if kind == "box":
        s = size
        pts = [(-s, 0, -s), (s, 0, -s), (s, 0, s), (-s, 0, s), (-s, 0, -s)]
        c = cmds.curve(n=name, d=1, p=pts)
    else:
        c = cmds.circle(n=name, r=size, nr=(0, 1, 0), ch=False)[0]
    sh = cmds.listRelatives(c, shapes=True)[0]
    cmds.setAttr(sh + ".overrideEnabled", 1)
    cmds.setAttr(sh + ".overrideColor", color)
    _tag(c)
    return c


def chains_from_roots(roots):
    chains = []
    for r in roots:
        chain = [r]
        cur = r
        while True:
            kids = cmds.listRelatives(cur, c=True, type="joint") or []
            if not kids:
                break
            if len(kids) > 1:
                _log("%s 有 %d 个子关节，只走 %s" % (cur, len(kids), kids[0]))
            cur = kids[0]
            chain.append(cur)
        chains.append(chain)
    return chains


def clean():
    n = 0
    for t in ("parentConstraint", "scaleConstraint"):
        for c in cmds.ls(type=t) or []:
            if cmds.attributeQuery(TAG, node=c, exists=True):
                cmds.delete(c)
                n += 1
    for node in cmds.ls("fk_ctrl_*_loc_fol", "fk_ctrl_*_loc_folGroup",
                        "fk_ctrl_*_loc_folGrp", "fk_ctrl_*_loc_folgrp",
                        "fk_zero_*_grp", "ik_zero_*_grp",
                        "fk_ctrl_*", "ik_ctrl_*", "*_plan", "*_plan_folGroup") or []:
        try:
            if cmds.attributeQuery(TAG, node=node, exists=True):
                cmds.delete(node)
                n += 1
        except Exception:
            pass
    for g in (GRP_ROOT, GRP_DRIVER, GRP_CTRL):
        if cmds.objExists(g) and cmds.attributeQuery(TAG, node=g, exists=True):
            cmds.delete(g)
            n += 1
    _log("清理 %d 个旧节点" % n)
    return n


def build(roots=None):
    if roots is None:
        roots = [r for r in (cmds.ls(sl=True, type="joint") or [])]
    if not roots:
        raise RuntimeError("先选中每条裙链的第一个关节")

    if cmds.ls("fk_ctrl_*_loc_fol"):
        clean()

    chains = chains_from_roots(roots)
    total = sum(len(c) for c in chains)
    _log("收集到 %d 条链 / %d 根骨骼" % (len(chains), total))

    grp_root = _ensure_grp(GRP_ROOT)
    grp_drv = _ensure_grp(GRP_DRIVER)
    grp_ctl = _ensure_grp(GRP_CTRL)

    # ---------- 面片 ----------
    patches = []
    for chain in chains:
        for b in chain:
            m = cmds.xform(b, q=True, ws=True, m=True)
            pl = cmds.polyPlane(w=PLAN_SIZE, h=PLAN_SIZE, sx=1, sy=1)[0]
            cmds.xform(pl, ws=True, m=m)
            patches.append(pl)

    plan = cmds.polyUnite(patches, n="fk_%s_plan" % roots[0], ch=False)[0]
    cmds.delete(plan, ch=True)
    cmds.select(plan, r=True)
    try:
        cmds.polyAutoProjection(plan, ch=True)
    except Exception as e:
        _log("自动投影失败：%s" % e)
    cmds.select(clear=True)
    cmds.delete(plan, ch=True)
    cmds.parent(plan, grp_root, r=True)
    _tag(plan)
    pshape = cmds.listRelatives(plan, shapes=True, type="mesh")[0]

    fol_grp = cmds.group(em=True, n="%s_folGroup" % plan)
    _tag(fol_grp)
    cmds.parent(fol_grp, grp_root, r=True)

    # ---------- 每节 ----------
    for ci, chain in enumerate(chains):
        prev_folgrp = None
        prev_fkctrl = None
        for b in chain:
            pos = cmds.xform(b, q=True, ws=True, t=True)
            cpm = cmds.createNode("closestPointOnMesh")
            cmds.connectAttr(pshape + ".outMesh", cpm + ".inMesh", f=True)
            cmds.setAttr(cpm + ".inPosition", pos[0], pos[1], pos[2], type="double3")
            cmds.dgdirty(a=True)
            u = cmds.getAttr(cpm + ".parameterU")
            v = cmds.getAttr(cpm + ".parameterV")
            cmds.delete(cpm)

            fol = cmds.createNode("follicle")
            fol_t = cmds.rename(cmds.listRelatives(fol, p=True)[0],
                                "fk_ctrl_%s_loc_fol" % b)
            fol = cmds.listRelatives(fol_t, shapes=True, type="follicle")[0]
            cmds.setAttr(fol + ".parameterU", u)
            cmds.setAttr(fol + ".parameterV", v)
            cmds.connectAttr(pshape + ".outMesh", fol + ".inputMesh", f=True)
            cmds.connectAttr(pshape + ".worldMatrix[0]", fol + ".inputWorldMatrix", f=True)
            _tag(fol_t)
            cmds.parent(fol_t, fol_grp, r=True)
            cmds.connectAttr(fol + ".outTranslate", fol_t + ".translate", f=True)
            cmds.connectAttr(fol + ".outRotate", fol_t + ".rotate", f=True)

            fol_lower = cmds.group(em=True, n="fk_ctrl_%s_loc_folGroup" % b)
            _tag(fol_lower)
            cmds.parent(fol_lower, fol_t, r=True)

            k1 = cmds.group(em=True, n="fk_ctrl_%s_loc_folGrp" % b)
            _tag(k1)
            cmds.parent(k1, grp_drv, r=True)
            cmds.xform(k1, ws=True, m=cmds.xform(b, q=True, ws=True, m=True))
            k2 = cmds.group(em=True, n="fk_ctrl_%s_loc_folgrp" % b)
            _tag(k2)
            cmds.parent(k2, k1, r=True)

            pc = cmds.parentConstraint(fol_lower, k2, mo=True,
                                       n="fk_ctrl_%s_loc_folgrp_parentConstraint1" % b)
            _tag(pc[0])
            if cmds.objExists(SCALE_REF):
                sc = cmds.scaleConstraint(SCALE_REF, k2,
                                          n="fk_ctrl_%s_loc_folgrp_scaleConstraint1" % b)
                _tag(sc[0])

            fz = cmds.group(em=True, n="fk_zero_%s_grp" % b)
            _tag(fz)
            cmds.parent(fz, grp_ctl, r=True)
            cmds.xform(fz, ws=True, m=cmds.xform(b, q=True, ws=True, m=True))
            fd = cmds.group(em=True, n="fk_driver_%s_grp" % b)
            _tag(fd)
            cmds.parent(fd, fz, r=True)
            fk_c = _make_curve("box", "fk_ctrl_%s" % b, BOX_SIZE, CTRL_COLOR_BOX)
            cmds.parent(fk_c, fd, r=True)

            iz = cmds.group(em=True, n="ik_zero_%s_grp" % b)
            _tag(iz)
            cmds.parent(iz, fk_c, r=True)
            idr = cmds.group(em=True, n="ik_driver_%s_grp" % b)
            _tag(idr)
            cmds.parent(idr, iz, r=True)
            ik_c = _make_curve("cir", "ik_ctrl_%s" % b, CIR_SIZE, CTRL_COLOR_CIR)
            cmds.parent(ik_c, idr, r=True)

            for ch in "trs":
                for ax in "xyz":
                    cmds.connectAttr(k2 + "." + ch + ax, fd + "." + ch + ax, f=True)

            pcb = cmds.parentConstraint(ik_c, b, mo=True, n="%s_parentConstraint1" % b)
            _tag(pcb[0])

            if prev_folgrp:
                cmds.parent(k1, prev_folgrp, absolute=True)
            if prev_fkctrl:
                cmds.parent(fz, prev_fkctrl, absolute=True)
            prev_folgrp = k2
            prev_fkctrl = fk_c
        _log("链 %d 完成（%d 节）" % (ci + 1, len(chain)))

    _log("全部完成：%d 条链 / %d 节" % (len(chains), total))
    return plan


def show_ui():
    if cmds.window("skirtFolRigWin", exists=True):
        cmds.deleteUI("skirtFolRigWin")
    cmds.window("skirtFolRigWin", t="裙子毛囊 Rig 生成器", w=380, h=220)
    cmds.columnLayout(adj=True, rs=8)
    cmds.text(l="选中每条裙链的第一个关节，然后点生成", h=30)
    cmds.button(l="生成整套 Rig", h=40, c=lambda *a: build())
    cmds.button(l="只清理生成物", h=30, c=lambda *a: clean())
    cmds.showWindow("skirtFolRigWin")


class SkirtFolRigNode(om.MPxNode):
    """市场的规范要求插件必须 registerNode，所以注册一个轻量节点。

    它本身只做数值透传（inValue → outValue），真正的功能由命令
    ``cmds.skirtFolRig()`` 完成（NODE_INFO.run 指向它）。
    """

    kNodeName = "skirtFolRigNode"
    kNodeId = om.MTypeId(0x00151503)

    aInValue = om.MObject()
    aOutValue = om.MObject()

    def __init__(self):
        super(SkirtFolRigNode, self).__init__()

    @staticmethod
    def creator():
        return SkirtFolRigNode()

    @staticmethod
    def initialize():
        n = om.MFnNumericAttribute()
        SkirtFolRigNode.aInValue = n.create("inValue", "iv",
                                           om.MFnNumericData.kDouble, 0.0)
        n.keyable = True
        n.storable = True
        SkirtFolRigNode.addAttribute(SkirtFolRigNode.aInValue)

        o = om.MFnNumericAttribute()
        SkirtFolRigNode.aOutValue = o.create("outValue", "ov",
                                            om.MFnNumericData.kDouble, 0.0)
        o.writable = False
        o.storable = False
        SkirtFolRigNode.addAttribute(SkirtFolRigNode.aOutValue)

        SkirtFolRigNode.attributeAffects(SkirtFolRigNode.aInValue,
                                         SkirtFolRigNode.aOutValue)

    def compute(self, plug, dataBlock):
        if plug == SkirtFolRigNode.aOutValue:
            v = dataBlock.inputValue(SkirtFolRigNode.aInValue).asDouble()
            dataBlock.outputValue(SkirtFolRigNode.aOutValue).setDouble(v)
            dataBlock.setClean(plug)


class SkirtFolRigCommand(om.MPxCommand):
    kName = "skirtFolRig"

    def __init__(self):
        super(SkirtFolRigCommand, self).__init__()

    @staticmethod
    def creator():
        return SkirtFolRigCommand()

    def isUndoable(self):
        return False

    def doIt(self, args):
        # 有选中关节就生成，没有就开窗口
        if cmds.ls(sl=True, type="joint"):
            build()
        else:
            show_ui()


def initializePlugin(plugin):
    pluginFn = om.MFnPlugin(plugin, "Heluo", "1.0.1", "Any")
    try:
        pluginFn.registerNode(SkirtFolRigNode.kNodeName,
                              SkirtFolRigNode.kNodeId,
                              SkirtFolRigNode.creator,
                              SkirtFolRigNode.initialize)
        _log("skirtFolRigNode registered")
    except Exception as e:
        _log("节点注册失败：%s" % e)
        raise
    try:
        pluginFn.registerCommand(SkirtFolRigCommand.kName,
                                 SkirtFolRigCommand.creator)
        _log("skirtFolRig command registered")
    except Exception as e:
        _log("命令注册失败：%s" % e)
        raise


def uninitializePlugin(plugin):
    pluginFn = om.MFnPlugin(plugin)
    for what, fn in (("命令", lambda: pluginFn.deregisterCommand(SkirtFolRigCommand.kName)),
                     ("节点", lambda: pluginFn.deregisterNode(SkirtFolRigNode.kNodeId))):
        try:
            fn()
            _log("%s 反注册完成" % what)
        except Exception as e:
            _log("%s 反注册失败：%s" % (what, e))
