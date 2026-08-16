# Lanerc Macast Bridge

让 Lanerc 的 DLNA 投屏在 Windows 电脑上通过
[Macast](https://github.com/xfangfang/Macast) 正常播放。

## 问题原因

Lanerc 的部分 HLS 视频分片以 `.jpg` 命名，并在 MPEG-TS 数据前附加一个很小的
JPEG 文件。Macast v0.7 内置的 mpv/FFmpeg 会把它误判为 MJPEG，随后提示：

```text
File error
no audio or video data played
```

本项目在 Macast 和播放器之间运行一个仅监听 `127.0.0.1` 的临时代理：

1. 重写 HLS 播放清单，隐藏会导致旧 FFmpeg 误判的 `.jpg` 文件名。
2. 检测 JPEG 结束标记及 MPEG-TS 同步字节。
3. 在内存中移除 JPEG 前缀，将标准 MPEG-TS 数据传给播放器。

视频采用边下边播方式，不会保存为完整视频文件。

## 要求

- Windows 10 或 Windows 11
- [Macast v0.7](https://github.com/xfangfang/Macast/releases/tag/v0.7)
- 可选：[PotPlayer](https://potplayer.daum.net/)

## 安装

退出 Macast，在 PowerShell 中运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

重新启动 Macast。安装器会自动选择：

1. 检测到 PotPlayer 时使用 `Lanerc PotPlayer Renderer`。
2. 否则使用 `Lanerc MPV Renderer`，即 Macast 自带的 mpv。

两个渲染器都会保留在 Macast 托盘菜单的“选择播放器”中，可以手动切换。
随后在 Lanerc 中像投电视一样选择 Macast 设备即可。

安装器会先将原配置备份到 Macast 配置目录下的 `backup` 文件夹。

## 卸载

退出 Macast 后运行：

```powershell
.\uninstall.ps1
```

## 工作方式

```text
Lanerc --DLNA--> Macast --local HLS bridge--> PotPlayer / mpv
```

- 代理只接受本机连接。
- 上游地址以 SHA-256 标识存放在内存中，不会出现在本地播放 URL 中。
- 普通 MP4 等非 HLS 媒体仍走播放器原有路径。

## 已知限制

- PotPlayer 渲染器支持播放和停止；DLNA 暂停、音量同步等控制受 PotPlayer 接口限制。
- 本项目针对 Macast v0.7 和当前观察到的 Lanerc HLS 分片格式。

## License

[MIT](LICENSE)
