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

## 发布到 Maya 节点插件市场

插件本体在这个仓库，市场索引在
[maya-node-plugin-index](https://github.com/MengXingXiaoMing/maya-node-plugin-index)。
上架分两步。

### 1. 插件放自己仓库（本仓库已完成）

```
nodes/<node_id>/<entry>.py
```

- 目录名必须是节点注册序号，本插件是 `0x00151503`
- 入口 `.py` 顶部必须有 `NODE_INFO`，其中 `node_id` / `node` / `version`
  要和索引条目完全一致
- 仓库必须是 **public**，索引校验会去读

### 2. 索引仓库加一条 JSON

Fork `maya-node-plugin-index`，在 `plugins/` 下新建 `0x00151503.json`：

```json
{
  "name": "裙子毛囊 Rig 生成器",
  "description": "按骨骼位置批量生成裙子的毛囊驱动 Rig。",
  "author": "禾洛",
  "version": "1.0.0",
  "node_id": "0x00151503",
  "node_name": "skirtFolRig",
  "category": "rigging",
  "tags": ["绑定", "裙子", "毛囊"],
  "repo": "sanque11/skirt-fol-rig",
  "subpath": "nodes/0x00151503",
  "entry": "skirt_fol_rig.py",
  "branch": "main",
  "maya_versions": ["2022", "2023", "2024", "2025"],
  "added": "2026-10-29",
  "updated": "2026-10-29"
}
```

提 PR 后 GitHub Actions 会自动校验并直接合并，`catalog.json` 自动重建，
市场刷新「在线」页就能看到。

### 发新版

改两处，版本号保持一致：

1. 插件里 `NODE_INFO["version"]`
2. 索引 `plugins/0x00151503.json` 的 `version` 和 `updated`

市场就会显示「可更新」。

### 踩过的坑

- **路径不能含中文**：Maya 的 `loadPlugin` 在中文路径下会报 UTF-8 解码错误
- 网页翻译会把 `nodes` 显示成「节点」，但真实路径仍是 `nodes`，别被误导
- 只改 `plugins/*.json` 的 PR 才会自动合并；动 `catalog.json` / `scripts/`
  要走人工审核
- `repo` 必须是 PR 作者**自己的公开仓库**，否则校验不过
- `category` 必须存在于 `categories.json`（本插件用 `rigging`）
