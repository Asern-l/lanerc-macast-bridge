# Lanerc Cast for Windows

[![Tests](https://github.com/Asern-l/lanerc-cast-windows/actions/workflows/tests.yml/badge.svg)](https://github.com/Asern-l/lanerc-cast-windows/actions/workflows/tests.yml) [![Latest release](https://img.shields.io/github/v/release/Asern-l/lanerc-cast-windows)](https://github.com/Asern-l/lanerc-cast-windows/releases/latest) [![License](https://img.shields.io/github/license/Asern-l/lanerc-cast-windows)](LICENSE)

Lanerc Cast for Windows 是一个社区维护的 Windows DLNA 接收与电视中转工具。它接收局域网内应用发起的 DLNA 投屏，在电脑播放器中播放，也可以选择使用 FFmpeg 将媒体转换为电视更容易接受的格式后再发送到电视。

本项目不提供视频内容、不修改 Lanerc 客户端、不处理登录凭据，也不提供账号验证绕过功能。它与 Lanerc、Macast、PotPlayer 或任何电视厂商没有官方隶属关系。

## 功能

- 将电脑显示为 DLNA 播放设备，接收 Lanerc 等应用的投屏请求；
- 自动修复带 PNG/JPEG 图片前缀的 HLS 分片，避免严格的 FFmpeg 将其误识别为图片；
- 电脑本地播放：优先使用 PotPlayer，也支持 Macast 内置播放器；
- 电视中转：使用 FFmpeg 转换为 H.264/AAC/MPEG-TS，并实时发现局域网电视；
- 支持手动指定 PotPlayer 路径和电视设备；
- 提供仅监听 `127.0.0.1` 的本地控制中心；
- 播放采用边传输边处理，不会主动保存完整视频文件。

## 下载与安装

推荐下载最新 Release：

[LanercCast-v2.3.1-win64-standalone.exe](https://github.com/Asern-l/lanerc-cast-windows/releases/download/v2.3.1/LanercCast-v2.3.1-win64-standalone.exe)

这个 EXE 是安装程序，不是日常启动入口。双击后选择一个专用的空目录，例如 `D:\LanercCast`。安装完成后会：

1. 将正式入口安装为 `LanercCast.exe`；
2. 创建桌面和开始菜单中的正常启动快捷方式；
3. 自动打开正式程序和本地控制中心；
4. 在 Windows“已安装的应用”中注册 Lanerc Cast。

以后请从快捷方式或安装目录中的 `LanercCast.exe` 启动，不要直接重复运行下载的安装包。安装器和正式程序均启用单实例保护。

本版本使用严格的安装标记，不会自动接管旧版目录。若电脑已有旧版，请先在 Windows“已安装的应用”中卸载旧版，再选择新的空目录安装。

卸载只需打开 Windows“设置 → 应用 → 已安装的应用”，找到 Lanerc Cast 并点击“卸载”。卸载仅清理本程序安装清单中的文件、注册信息和快捷方式，不会递归删除安装目录中的其他文件；安装前存在的 Macast 配置会被恢复。

### 运行目录

默认安装目录：

```text
D:\LanercCast
```

实际安装目录可在安装器中自定义。运行组件、配置、日志和备份均位于所选目录下；PotPlayer 是可选的独立软件，不会由本项目删除。

## 使用

### 电脑播放

1. 启动 Lanerc Cast；
2. 在控制中心选择“本机播放”；
3. 选择 PotPlayer 或内置播放器；
4. 在手机应用中选择电脑上的 DLNA 设备进行投屏。

### 电视中转

1. 在控制中心选择“电视播放”；
2. 扫描并选择同一局域网中的电视；
3. 选择电视声音或电脑声音输出；
4. 保存设置后，从手机应用投屏到 Lanerc Cast。

电视端的 DLNA 缓冲和进度上报由电视固件决定。电脑声音与电视画面分离属于实验性模式，可能需要调整延迟；如果优先稳定播放，请让声音随电视输出。

## 工作方式

```text
手机应用 ──DLNA──> Lanerc Cast / Macast
                         ├── HLS 图片前缀修复 ──> PotPlayer / 内置播放器
                         └── FFmpeg 转码 ──DLNA──> 电视
```

控制中心和本地媒体代理默认只监听 `127.0.0.1`。电视发现依赖局域网 SSDP/DLNA；VPN、虚拟网卡、访客网络隔离和 Windows 防火墙可能阻止发现。

## 故障排查

- **手机找不到电脑设备**：确认电脑和手机在同一局域网，允许 Macast 通过 Windows 专用网络防火墙；
- **找不到电视**：在电视上开启 DLNA/媒体投放，关闭 VPN 或网络隔离后重新扫描；
- **电视无法播放**：确认控制中心显示 FFmpeg 已就绪，并查看安装目录 `config\Macast\lanerc_tv.log`；
- **电脑能播、电视不能播**：确认使用 v2.3.1 或更高版本，该版本包含 PNG/JPEG 前缀分片修复；
- **音画不同步**：优先使用电视声音输出，或关闭自动读取进度并调整固定延迟。

## 开发

需要 Windows 10/11、Python 3.10+ 和测试依赖。运行测试：

```powershell
python -m unittest discover -s tests -v
```

控制中心页面的浏览器测试：

```powershell
python tests\playwright_pro.py
```

仓库中的 `launcher.py` 是安装器和已安装启动器的共同入口。发布 EXE 时，需要将 Macast、FFmpeg 和许可证文件放入构建暂存目录，再使用 PyInstaller spec 打包。

## 许可证

本项目自身代码采用 [MIT License](LICENSE)。随 EXE 分发的 Macast 和 FFmpeg 组件分别遵循 GPLv3，许可证文本和来源说明见 [`third_party/`](third_party/)。

## 贡献与安全

提交问题前请阅读 [贡献指南](CONTRIBUTING.md)，并删除日志中的账号、Cookie、完整媒体地址和私人 IP。安全问题请按照 [安全策略](SECURITY.md) 私下报告，不要直接发布到公开 Issue。
