# Lanerc Cast

[![Tests](https://github.com/Asern-l/lanerc-macast-bridge/actions/workflows/tests.yml/badge.svg)](https://github.com/Asern-l/lanerc-macast-bridge/actions/workflows/tests.yml) [![Latest release](https://img.shields.io/github/v/release/Asern-l/lanerc-macast-bridge)](https://github.com/Asern-l/lanerc-macast-bridge/releases/latest) [![License](https://img.shields.io/github/license/Asern-l/lanerc-macast-bridge)](LICENSE)

Lanerc Cast 是面向 Windows 的 Macast 兼容扩展，让 Lanerc 的 DLNA 投屏可以在电脑播放器中可靠播放，并可选通过电脑转码后发送到电视。

> 本项目为社区兼容工具，与 Lanerc、Macast、PotPlayer 或电视厂商无官方隶属关系。

## 主要功能

- 修复部分 Lanerc HLS 分片带 JPEG 前缀而无法播放的问题；
- 自动选择已安装的 PotPlayer，未安装时使用 Macast 内置播放器；
- 支持手动填写 PotPlayer 程序路径，非标准安装位置也可使用；
- 实时发现同一局域网中的 DLNA 电视；
- 使用 FFmpeg 转码为兼容性较高的 H.264、AAC 和 MPEG-TS；
- 可选将电视画面与电脑声音分离，用于连接电脑的耳机；
- 提供仅监听本机的控制中心，集中管理播放位置、电视和声音设置；
- 保留升级前配置备份，更新版本时不重置用户选择。

媒体采用边传输边播放，不会保存为完整视频文件。

## 项目定位

这是一个独立的社区兼容项目，目标是让 Windows 用户直接接收 Lanerc 的 DLNA 投屏。它不提供视频内容、不绕过账号验证，也不修改 Lanerc 客户端。

## 系统要求

- Windows 10 或 Windows 11；
- PotPlayer（可选，本机播放和电脑声音输出推荐）。

EXE 已内置 Macast 0.7 运行引擎和 FFmpeg，不需要用户另外安装。首次运行会让你选择运行时目录（例如 `D:\LanercCast`），之后会记住该位置；如果不更改，默认使用 `%LOCALAPPDATA%\LanercCast`。

## 安装

### EXE（推荐）

从 [Releases](https://github.com/Asern-l/lanerc-macast-bridge/releases) 下载 `LanercCast-v2.3.1-win64-standalone.exe`，直接双击运行。它是安装程序：首次运行选择专用安装目录后，会复制正式入口 `LanercCast.exe`、创建桌面和开始菜单快捷方式，并自动打开正式程序。以后请从快捷方式或安装目录中的 `LanercCast.exe` 启动；安装程序支持重新运行进行升级。

卸载只需在 Windows“已安装的应用”中选择 Lanerc Cast。卸载仅删除本程序安装清单中的内容，不会递归删除安装目录中的其他文件。

本版本使用独立安装标记。旧版目录不会被自动接管；请先手动清理旧版，或选择新的空安装目录。

该社区构建暂未使用商业代码签名证书，Windows SmartScreen 可能在首次运行时显示提醒。可在 Release 页面核对 SHA-256。

### PowerShell

源码安装方式仍需自行准备 Macast 0.7；电视播放还需准备 FFmpeg。

1. 从 Macast 托盘菜单完全退出 Macast。
2. 在 PowerShell 中进入项目目录并运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

3. 重新启动 Macast。
4. 打开 [http://127.0.0.1:4380/](http://127.0.0.1:4380/) 进入控制中心。

安装程序会自动检测 PotPlayer 和 FFmpeg，并将原配置备份到 Macast 配置目录的 `backup` 文件夹。升级安装会保留当前播放位置、电视和声音设置。

## 使用

### 本机播放

在控制中心选择“本机播放”，再选择 PotPlayer 或 Macast 内置播放器。随后在 Lanerc 中投屏到 Macast 设备。

### 电视播放

1. 选择“电视播放”；
2. 扫描并选择目标电视；
3. 选择声音随电视输出或从电脑输出；
4. 保存设置后，在 Lanerc 中投屏到 Macast 设备。

“随电视输出”同步最稳定。“从电脑输出”属于实验性功能：电视的 DLNA 缓冲时间通常不会通过标准接口准确上报，因此可能需要调整固定声音延迟。

## 工作方式

```text
Lanerc ──DLNA──> Macast / Lanerc Cast
                       ├── HLS 修复 ──> PotPlayer / 内置播放器
                       └── FFmpeg 转码 ──DLNA──> 电视
```

控制中心仅监听 `127.0.0.1`。上游媒体地址在本地代理中以哈希标识保存，不直接暴露在代理 URL 中。

## 故障排查

### 找不到电视

- 确认电脑和电视位于同一局域网；
- 在电视上开启 DLNA 或媒体投放功能；
- 暂时关闭 VPN、虚拟网卡或网络隔离后重新扫描；
- 允许 Macast 通过 Windows 专用网络防火墙。

### 电视无法播放

- 在控制中心“运行环境”中确认 FFmpeg 已就绪；
- 查看 `lanerc_tv.log` 和 `lanerc_cast.log`；
- 部分电视会对实时流缓存数秒，这是电视端行为。

### 音画不同步

优先选择“随电视输出”。电脑声音输出无法保证所有电视自动同步，可关闭“尝试读取电视播放进度”并调整固定声音延迟。

## 卸载

完全退出 Macast 后运行：

```powershell
.\uninstall.ps1
```

## 开发验证

```powershell
python -m unittest discover -s tests -v
python tests\playwright_pro.py
```

## License

本项目代码采用 [MIT License](LICENSE)。随 EXE 分发的 Macast 和 FFmpeg 组件分别遵循其 GPLv3 许可证，相关文本和来源说明见 [`third_party/`](third_party/)。

## 参与贡献

欢迎提交可复现的问题报告、兼容性信息和改进建议。提交前请先阅读 [贡献指南](CONTRIBUTING.md)，不要在 Issue 或日志中粘贴账号、Cookie、完整媒体地址或私人 IP 信息。
