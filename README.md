# 裙子毛囊 Rig 生成器（Maya 节点插件）

按骨骼位置批量生成裙子的毛囊驱动 Rig。适用于裙子、飘带、披风这类需要「贴布料 + 手动 FK」的部件。

## 功能

- 按每根骨骼位置生成小面片（0.01，1×1），全部合并成一个 mesh 并自动投影 UV
- 在合并面片上按骨骼位置反查 UV 建毛囊
- 两层空组（静态基准层 + 0 层），0 层被毛囊下层组父对象约束
- 方块控制器（FK，整链摆动）+ 圆控制器（单节微调）
- 自动 `parentConstraint` 骨骼、链式嵌套、重跑自动清理

## 安装

Maya 里运行：

```python
import maya.cmds as cmds
cmds.loadPlugin(r"路径/0x00151503/skirt_fol_rig.py")
```

或者放到 `Documents/maya/scripts/` 下，在 `userSetup.py` 里加载。

> ⚠️ 插件所在路径**不要含中文**，Maya 加载 .py 插件时会报 UTF-8 解码错误。

## 使用

1. 建好裙子骨骼（链式父子关系）
2. 选中**每条链的第一个关节**
3. 运行 `cmds.skirtFolRig()`
4. 把生成的 `fk_XXX_plan` 面片手动蒙皮给身体骨骼
5. 方块控制器摆整条链，圆控制器调单节

重跑会自动清理上次生成物。

## 生成的节点结构

```
fk_XXX_plan                      全部面片合并后的 mesh
fk_ctrl_XXX_loc_fol              毛囊（t/r ← 毛囊输出）
  └ fk_ctrl_XXX_loc_folGroup     毛囊下层组（0 层）
fk_ctrl_XXX_loc_folGrp           空组第一层（静态对齐骨骼，按链嵌套）
  └ fk_ctrl_XXX_loc_folgrp       空组第二层（0 层）← 被毛囊下层组约束
      └─connect t/r/s─→ fk_driver_XXX_grp
fk_zero_XXX_grp → fk_driver_XXX_grp → fk_ctrl_XXX        方块 0.5
    └ ik_zero_XXX_grp → ik_driver_XXX_grp → ik_ctrl_XXX  圆 1.0 → 约束骨骼
```

## 参数

文件顶部常量可改：

| 常量 | 默认 | 说明 |
|---|---|---|
| `PLAN_SIZE` | 0.01 | 面片尺寸 |
| `BOX_SIZE` | 0.5 | 方块控制器 |
| `CIR_SIZE` | 1.0 | 圆控制器 |
| `GRP_ROOT` / `GRP_DRIVER` / `GRP_CTRL` | `Skirt_Grp` 等 | 输出组名，不存在会自动建 |
| `SCALE_REF` | `local_C0_ctl` | 缩放参考，不存在则跳过 |

## 兼容

Maya 2022 / 2023 / 2024 / 2025（2022 mayapy 实测）。

## 许可

MIT
