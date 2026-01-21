# Claude Code 通知系统使用指南

本指南介绍如何使用 Claude Code 的通知系统，包括窗口高亮和声音提醒功能。

## 概述

通知系统支持两个版本：
- **Python 版本** (`/notify`) - 需要 Python 环境
- **PowerShell 版本** (`/notify-powershell`) - 无需额外依赖

两个版本功能完全相同，都支持**全局配置**和**项目配置**。

---

## 快速开始

### 基本命令

```bash
# 查看当前状态
/notify
/notify-powershell

# 启用通知
/notify enable
/notify-powershell enable

# 禁用通知
/notify disable
/notify-powershell disable

# 只关闭声音（保留窗口高亮）
/notify sound-off
/notify-powershell sound-off

# 只关闭窗口高亮（保留声音）
/notify highlight-off
/notify-powershell highlight-off
```

---

## 全局 vs 项目配置

### 配置层级

```
全局配置 (~/.claude/notification_config.json)
    ↓ 默认设置
项目配置 (.claude/notification_config.json)
    ↓ 覆盖设置
最终有效配置
```

### 全局配置

适用于所有项目，设置一次，所有项目生效。

```bash
# 全局启用通知
/notify enable --global
/notify-powershell enable --global

# 全局禁用通知
/notify disable --global
/notify-powershell disable --global

# 查看全局配置状态
/notify status --global
/notify-powershell status --global
```

### 项目配置

只对当前项目生效，会覆盖全局配置。

```bash
# 禁用当前项目的通知
/notify disable
/notify-powershell disable

# 只关闭当前项目的声音
/notify sound-off
/notify-powershell sound-off
```

---

## 使用场景

### 场景 1：日常使用 - 全局启用

```bash
# 第一次设置：全局启用所有通知
/notify enable --global

# 之后所有新项目都会默认启用通知
```

### 场景 2：嘈杂项目 - 项目禁用

```bash
# 对频繁触发通知的项目单独禁用
/notify disable

# 该项目不再有通知，其他项目不受影响
```

### 场景 3：工作环境 - 只用视觉提醒

```bash
# 全局禁用声音，保留窗口高亮
/notify sound-off --global
```

### 场景 4：重要项目 - 增强提醒

```bash
# 项目级别重新启用通知（覆盖全局禁用）
/notify enable
```

---

## 状态显示

运行 `/notify` 或 `/notify-powershell` 查看详细状态：

```
Claude Code Notification Status
===================================

Configuration Files:
  [+] Global: C:\Users\YourName\.claude\notification_config.json
  [+] Project: .claude\notification_config.json

  [+] Notifications: Enabled
     (from: project)
  [+] Sound: Enabled
     (from: project)
  [+] Window Highlight: Enabled
     (from: project)

Event Settings:
  [+] stop: sound, highlight
  [+] tool_complete: sound, highlight
  [+] permission: highlight
  [+] error: sound, highlight

Note: Project config is overriding global settings.
      Use 'disable' or delete the project config to remove overrides.
```

### 状态说明

- `[+]` 表示已启用
- `[ ]` 表示已禁用
- `(from: global)` - 来自全局配置
- `(from: project)` - 来自项目配置
- `(from: default)` - 使用默认值

---

## 配置文件位置

| 配置类型 | 位置 | 作用范围 |
|---------|------|---------|
| 全局配置 | `~/.claude/notification_config.json` | 所有项目 |
| 项目配置 | `.claude/notification_config.json` | 当前项目 |
| 声音文件 | `.claude/mp3/*.mp3` | 当前项目 |

---

## 通知事件

系统支持以下事件的通知：

| 事件 | 触发时机 | 默认设置 |
|-----|---------|---------|
| `stop` | 会话结束 | 声音 + 高亮 |
| `tool_complete` | 工具执行完成 | 声音 + 高亮 |
| `permission` | 请求权限 | 仅高亮 |
| `error` | 发生错误 | 声音 + 高亮 |

---

## 自定义声音

### 替换默认声音文件

将你的 MP3 文件放到 `.claude/mp3/` 目录：

```
.claude/mp3/
├── notice.mp3           # 默认通知音
├── complete.mp3         # 会话结束
├── tool_complete.mp3    # 工具完成
├── permission.mp3       # 权限请求
└── error.mp3            # 错误提示
```

**注意**：系统支持 MP3 和 WAV 格式。

---

## 故障排查

### 没有声音

1. **检查配置是否启用**
   ```bash
   /notify status
   ```

2. **检查声音文件是否存在**
   ```bash
   # 确认声音文件存在
   dir .claude\mp3\
   ```

3. **测试播放**
   ```bash
   # PowerShell 版本测试
   powershell -ExecutionPolicy Bypass -File .claude/scripts/notify.ps1 -Event tool_complete
   ```

### 只有系统提示音

这通常表示：
- 声音文件格式不正确
- 声音文件路径错误
- 播放器加载失败

解决方法：确认声音文件是有效的 MP3 或 WAV 格式。

### 通知没有触发

检查配置文件：
```bash
# 查看配置
/notify status

# 确认配置文件存在且有效
dir .claude\notification_config.json
```

---

## 配置文件格式

你可以手动编辑配置文件：

```json
{
  "enabled": true,
  "sound_enabled": true,
  "highlight_enabled": true,
  "events": {
    "stop": {
      "enabled": true,
      "sound": true,
      "highlight": true,
      "flash_count": 5,
      "highlight_mode": "flash"
    },
    "tool_complete": {
      "enabled": true,
      "sound": true,
      "highlight": true,
      "flash_count": 3,
      "highlight_mode": "flash"
    },
    "permission": {
      "enabled": true,
      "sound": false,
      "highlight": true,
      "flash_count": 0,
      "highlight_mode": "focus"
    },
    "error": {
      "enabled": true,
      "sound": true,
      "highlight": true,
      "flash_count": 5,
      "highlight_mode": "flash"
    }
  }
}
```

### 配置选项说明

| 选项 | 说明 |
|-----|------|
| `enabled` | 总开关 |
| `sound_enabled` | 声音总开关 |
| `highlight_enabled` | 窗口高亮总开关 |
| `events.*.enabled` | 单个事件的开关 |
| `events.*.sound` | 单个事件的声音开关 |
| `events.*.highlight` | 单个事件的高亮开关 |
| `events.*.flash_count` | 闪烁次数 |
| `events.*.highlight_mode` | 高亮模式 (flash/focus/topmost/all) |

---

## 删除项目配置

如果要让项目使用全局配置，删除项目配置文件：

```bash
# Windows
del .claude\notification_config.json

# Linux/Mac
rm .claude/notification_config.json
```

---

## 版本选择建议

| 使用场景 | 推荐版本 | 原因 |
|---------|---------|------|
| Windows 系统 | PowerShell 版本 | 无需依赖，性能更好 |
| Linux/Mac | Python 版本 | 系统自带 Python |
| 需要跨平台 | Python 版本 | 兼容性更好 |

---

## 常见问题

### Q: 两个版本可以同时使用吗？

A: 不建议。使用其中一个版本即可，功能完全相同。

### Q: 配置文件可以手动编辑吗？

A: 可以，但建议使用命令行工具，避免格式错误。

### Q: 如何重置所有设置？

A: 删除配置文件，系统会使用默认值：
```bash
# 重置全局配置
del ~/.claude/notification_config.json

# 重置项目配置
del .claude/notification_config.json
```

### Q: 通知会影响性能吗？

A: 影响极小。声音播放是同步的，但通常很短（<2秒）。

---

## 技术支持

如有问题，请检查：
1. PowerShell 版本需要 5.1+
2. Python 版本需要 Python 3.6+
3. 配置文件格式是否正确
4. 声音文件是否存在且格式正确

---

**最后更新**: 2026-01-20
